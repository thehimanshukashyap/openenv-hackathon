---
title: Incident Response Triage Environment
emoji: 🚨
colorFrom: red
colorTo: yellow
sdk: docker
pinned: false
app_port: 7860
tags:
  - openenv
  - incident-response
  - reinforcement-learning
  - sre
---

# Incident Response Triage Environment

An OpenEnv-compatible reinforcement learning environment for training and evaluating agents on realistic production incident handling. The agent assumes the role of an on-call Site Reliability Engineer (SRE): inspect alerts, query logs and metrics, identify the root cause, apply the appropriate mitigation, and verify recovery.

---

## Motivation

Production incident response is a high-stakes, high-complexity workflow that is ideal for agent evaluation:

- The first visible alert is rarely the root cause.
- Partial progress matters — investigation quality has value before the final fix.
- Incorrect actions can actively worsen an incident.

This environment models those properties through multi-step trajectories, progressive reward shaping, and structured difficulty progression across three tasks.

---

## Round 1 Requirement Compliance

| Requirement | Status |
|---|---|
| Real-world task (not a game or toy) | SRE incident triage |
| Minimum 3 tasks with difficulty range | `easy`, `medium`, `hard` |
| Full OpenEnv API: `reset()`, `step()`, `state()` | Implemented |
| Typed Pydantic models for Observation, Action, Reward | Implemented |
| Scores bounded to `[0.0, 1.0]` | Implemented |
| `openenv.yaml` with metadata | Included |
| Meaningful reward function with partial progress | Implemented |
| Baseline inference script (`inference.py`) using OpenAI client | Included |
| Reads credentials from environment variables | `HF_TOKEN`, `API_BASE_URL`, `MODEL_NAME` |
| Structured `[START]` / `[STEP]` / `[END]` stdout logs | Implemented |
| Dockerized and HF Space compatible | `Dockerfile`, port `7860` |
| README with description, spaces, tasks, setup, and scores | This document |

---

## Task Definitions

| Task | Scenario | Core Challenge | Max Steps |
|---|---|---|---|
| `easy` | Single-service incident | Obvious root cause directly identifiable from logs | 10 |
| `medium` | Cascading dependency failure | Distinguish symptom service from the actual root cause service | 18 |
| `hard` | Intermittent race condition | Misleading alerts with a subtle hidden signal requiring deeper investigation | 25 |

**Difficulty progression:**
- `easy` — Direct diagnosis and mitigation from surface-level signals.
- `medium` — Requires dependency tracing via `query_dependencies` to distinguish cause from effect.
- `hard` — Requires cross-signal correlation despite normal-looking surface metrics and misleading alerts.

---

## Action Space

All actions are submitted as JSON payloads to the `/step` endpoint.

```json
{"action_type": "query_logs",        "target_service": "<service>", "log_level": "ERROR", "task_name": "<task>"}
{"action_type": "query_metrics",     "target_service": "<service>", "task_name": "<task>"}
{"action_type": "query_alerts",      "task_name": "<task>"}
{"action_type": "query_dependencies","target_service": "<service>", "task_name": "<task>"}
{"action_type": "identify_cause",    "suspected_service": "<service>", "suspected_cause": "<cause>", "task_name": "<task>"}
{"action_type": "take_action",       "mitigation": "<mitigation>", "task_name": "<task>"}
{"action_type": "verify_recovery",   "task_name": "<task>"}
```

### Enumerated Values

**Services:** `api-gateway`, `auth-service`, `payment-service`, `user-service`, `cache-service`, `db-primary`, `notification-svc`

**Root causes:** `OOM`, `BAD_DEPLOY`, `CONFIG_ERROR`, `DISK_FULL`, `DB_CONN_LIMIT`, `RACE_CONDITION`

**Mitigations:** `restart_service`, `rollback_deploy`, `fix_config`, `scale_out`, `cleanup_disk`, `increase_db_pool`, `flush_cache`, `escalate_to_human`, `increase_timeout`

---

## Observation Space

Each `/step` and `/reset` response returns an observation object:

```json
{
  "task_name":       "easy|medium|hard",
  "task_description":"string",
  "system_overview": {"<service>": {"status": "HEALTHY|DEGRADED", "error_rate": 0.0}},
  "active_alerts":   [{"alert_name": "string", "service": "string", "severity": "string"}],
  "query_result":    {"...": "..."},
  "action_result":   "string|null",
  "reward":          0.0,
  "done":            false,
  "step_count":      0,
  "message":         "string"
}
```

Episode state is returned by `/state`:

```json
{
  "episode_id":               "string",
  "task_name":                "easy|medium|hard",
  "step_count":               0,
  "max_steps":                10,
  "done":                     false,
  "root_cause_identified":    false,
  "correct_cause_identified": false,
  "mitigation_taken":         false,
  "correct_mitigation_taken": false,
  "recovery_verified":        false,
  "cumulative_reward":        0.0,
  "score":                    0.0
}
```

---

## Reward and Scoring

Reward is shaped across the full trajectory — not sparse end-of-episode:

- **Investigation rewards** for useful diagnostic queries.
- **Partial credit** for partially correct diagnosis.
- **Penalties** for unsafe or incorrect mitigation actions.
- **Efficiency penalty** applied after the task-specific optimal step budget is exceeded.

**Final score breakdown** (bounded to `[0.0, 1.0]`):

| Milestone | Score Weight |
|---|---|
| Correct root cause identified | +0.35 |
| Correct mitigation applied | +0.40 |
| Recovery verified | +0.15 |
| Efficiency bonus (within optimal steps) | +0.10 |

---

## API Reference

| Endpoint | Method | Description |
|---|---|---|
| `/health` | GET | Liveness probe |
| `/schema` | GET | Supported action types and enumerated value vocabulary |
| `/reset?task_name=<task>` | POST | Start or reset an episode for the selected task |
| `/step` | POST | Execute one agent action and receive an observation |
| `/state?task_name=<task>` | GET | Current episode state and normalized score |

---

## Local Setup

### 1. Install dependencies

```bash
pip install -r server/requirements.txt
pip install openai requests
```

### 2. Start the server

```bash
uvicorn server.app:app --host 0.0.0.0 --port 8000
```

### 3. Verify the server is running

```bash
curl http://localhost:8000/health
curl http://localhost:8000/schema
```

---

## Docker Usage

```bash
docker build -t incident-response-env -f server/Dockerfile .
docker run -p 8000:7860 incident-response-env
```

Verify the container is running:

```bash
curl http://localhost:8000/health
```

---

## Baseline Inference

`inference.py` runs all three tasks and emits validator-compatible structured logs to stdout.

**Required log format:**

```
[START] task=<task_name> env=<benchmark> model=<model_name>
[STEP]  step=<n> action=<type> reward=<r> done=<true|false> error=<msg|null>
[END]   success=<true|false> steps=<n> score=<score> rewards=<r1,r2,...>
```

**Environment variables:**

```bash
set HF_TOKEN=<your_hf_token>
set API_BASE_URL=https://router.huggingface.co/v1
set MODEL_NAME=Qwen/Qwen2.5-72B-Instruct
set ENV_URL=http://localhost:8000
python inference.py
```

---

## Baseline Scores

Record the latest baseline run values here before submission:

| Task | Score |
|---|---|
| easy | 0.4 |
| medium | 0.4 |
| hard | 0.2 |
| average | 0.33 |

Scores must remain in `[0.0, 1.0]`. For reproducibility, keep the model and API endpoint fixed across runs.

---

## Validation and Tests

Run the full functional test suite:

```bash
python test_full.py
```

Expected result: all tests passing (`123/123` at time of writing).
