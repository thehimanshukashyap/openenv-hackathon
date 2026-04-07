"""
Incident Response Triage — Baseline Inference Script
=====================================================
Runs an LLM agent against all 3 tasks (easy / medium / hard) and prints
progress in the exact format required by the OpenEnv validator.

Required environment variables:
  API_BASE_URL  — e.g. https://router.huggingface.co/v1
  MODEL_NAME    — e.g. Qwen/Qwen2.5-72B-Instruct
  HF_TOKEN      — your HuggingFace token
  ENV_URL       — base URL of the running environment server (default: http://localhost:8000)

Output format (mandatory — validator checks exact field names and order):
  [START] task=<task> env=incident-response-env model=<model>
  [STEP]  step=<n> action=<type> reward=<r> done=<bool> error=null
  [END]   success=<bool> steps=<n> score=<s> rewards=<csv>
"""

import os
import sys
import json
import requests
from openai import OpenAI

# ── Config ────────────────────────────────────────────────────────────────────
API_BASE_URL = os.getenv("API_BASE_URL", "https://router.huggingface.co/v1")
MODEL_NAME   = os.getenv("MODEL_NAME",   "Qwen/Qwen2.5-72B-Instruct")
HF_TOKEN     = os.getenv("HF_TOKEN",     "")
ENV_URL      = os.getenv("ENV_URL",      "http://localhost:8000")

TASKS     = ["easy", "medium", "hard"]
MAX_STEPS = {"easy": 10, "medium": 18, "hard": 25}

client = OpenAI(api_key=HF_TOKEN, base_url=API_BASE_URL)

# ── System prompt ─────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are an expert SRE (Site Reliability Engineer) responding to a live production incident.
Your job is to investigate the system, find the root cause, and apply the correct fix.

AVAILABLE ACTION TYPES (respond with ONLY valid JSON — no explanation, no markdown):

1. query_logs
   {"action_type":"query_logs","target_service":"<svc>","log_level":"ERROR","task_name":"<task>"}

2. query_metrics
   {"action_type":"query_metrics","target_service":"<svc>","task_name":"<task>"}

3. query_alerts
   {"action_type":"query_alerts","task_name":"<task>"}

4. query_dependencies  (use for medium/hard tasks to trace cascading failures)
   {"action_type":"query_dependencies","target_service":"<svc>","task_name":"<task>"}

5. identify_cause  (commit your diagnosis before taking action)
   {"action_type":"identify_cause","suspected_service":"<svc>","suspected_cause":"<cause>","task_name":"<task>"}

6. take_action  (apply the mitigation)
   {"action_type":"take_action","mitigation":"<mitigation>","task_name":"<task>"}

7. verify_recovery  (confirm service is healthy — closes the episode)
   {"action_type":"verify_recovery","task_name":"<task>"}

SERVICES: api-gateway, auth-service, payment-service, user-service, cache-service, db-primary, notification-svc

ROOT CAUSES: OOM, BAD_DEPLOY, CONFIG_ERROR, DISK_FULL, DB_CONN_LIMIT, RACE_CONDITION

MITIGATIONS:
  OOM           → scale_out  or  restart_service
  BAD_DEPLOY    → rollback_deploy
  CONFIG_ERROR  → fix_config
  DISK_FULL     → cleanup_disk
  DB_CONN_LIMIT → increase_db_pool
  RACE_CONDITION→ fix_config

STRATEGY:
1. query_alerts first to see what's firing
2. query_logs (with log_level=ERROR) for suspicious services
3. query_metrics for the most suspicious service
4. For medium/hard: use query_dependencies to trace cascading failures
5. identify_cause once confident
6. take_action with the correct mitigation
7. verify_recovery to close the episode

Respond with ONLY the JSON action object. Nothing else."""


# ── Environment client helpers ────────────────────────────────────────────────

def call_reset(task_name: str) -> dict:
    r = requests.post(f"{ENV_URL}/reset", params={"task_name": task_name}, timeout=10)
    r.raise_for_status()
    return r.json()


def call_step(payload: dict) -> dict:
    r = requests.post(f"{ENV_URL}/step", json=payload, timeout=10)
    r.raise_for_status()
    return r.json()


def call_state(task_name: str) -> dict:
    r = requests.get(f"{ENV_URL}/state", params={"task_name": task_name}, timeout=10)
    r.raise_for_status()
    return r.json()


# ── LLM call ─────────────────────────────────────────────────────────────────

def get_action(messages: list) -> str:
    resp = client.chat.completions.create(
        model=MODEL_NAME,
        messages=messages,
        max_tokens=200,
        temperature=0.2,
    )
    return resp.choices[0].message.content.strip()


# ── Task runner ───────────────────────────────────────────────────────────────

def run_task(task_name: str) -> float:
    obs = call_reset(task_name)

    print(f"[START] task={task_name} env=incident-response-env model={MODEL_NAME}")
    sys.stdout.flush()

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"TASK: {task_name}\n"
                f"DESCRIPTION: {obs['task_description']}\n\n"
                f"SYSTEM STATUS:\n{json.dumps(obs['system_overview'], indent=2)}\n\n"
                f"ACTIVE ALERTS:\n{json.dumps(obs['active_alerts'], indent=2)}\n\n"
                "Begin investigation. Respond with your first action as JSON."
            ),
        },
    ]

    rewards: list[float] = []
    step = 0
    raw_action = ""

    for step in range(1, MAX_STEPS[task_name] + 1):
        # Get action from LLM
        error_str = "null"
        try:
            raw_action = get_action(messages)
            action = json.loads(raw_action)
            action["task_name"] = task_name  # ensure correct task
        except json.JSONDecodeError as e:
            error_str = f"json_parse_error"
            action = {"action_type": "query_alerts", "task_name": task_name}
            raw_action = json.dumps(action)
        except Exception as e:
            error_str = "llm_error"
            action = {"action_type": "query_alerts", "task_name": task_name}
            raw_action = json.dumps(action)

        # Step environment
        try:
            obs = call_step(action)
        except Exception as e:
            error_str = "env_error"
            obs = {"reward": 0.0, "done": False, "message": str(e), "query_result": None}

        reward = obs.get("reward", 0.0)
        done   = obs.get("done", False)
        rewards.append(reward)

        print(
            f"[STEP] step={step} action={action.get('action_type', 'unknown')} "
            f"reward={reward:.2f} done={str(done).lower()} error={error_str}"
        )
        sys.stdout.flush()

        # Update conversation with result
        messages.append({"role": "assistant", "content": raw_action})
        messages.append({
            "role": "user",
            "content": (
                f"Result: {obs.get('message', '')}\n"
                f"Query result: {json.dumps(obs.get('query_result') or {})}\n"
                f"Step: {step}/{MAX_STEPS[task_name]}\n"
                "Next action (JSON only):"
            ),
        })

        if done:
            break

    # Final score
    state  = call_state(task_name)
    score  = state.get("score", 0.0)
    success = score >= 0.5
    rewards_str = ",".join(f"{r:.2f}" for r in rewards)

    print(
        f"[END] success={str(success).lower()} steps={step} "
        f"score={score:.2f} rewards={rewards_str}"
    )
    sys.stdout.flush()
    return score


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    if not HF_TOKEN:
        print("WARNING: HF_TOKEN not set. LLM calls will fail.", file=sys.stderr)

    scores = {}
    for task in TASKS:
        try:
            scores[task] = run_task(task)
        except Exception as e:
            print(f"ERROR running task {task}: {e}", file=sys.stderr)
            scores[task] = 0.0

    avg = sum(scores.values()) / len(scores)
    print(f"\nSummary: easy={scores['easy']:.2f} medium={scores['medium']:.2f} "
          f"hard={scores['hard']:.2f} avg={avg:.2f}")


if __name__ == "__main__":
    main()
