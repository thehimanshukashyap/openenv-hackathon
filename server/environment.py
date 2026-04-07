"""
Core Incident Response Triage Environment.
Handles episode state, action dispatch, reward calculation, and scoring.
"""

import uuid
import random
from typing import Optional

try:
    from server.scenarios.task_easy import generate_easy_scenario
    from server.scenarios.task_medium import generate_medium_scenario
    from server.scenarios.task_hard import generate_hard_scenario
except ImportError:
    from scenarios.task_easy import generate_easy_scenario
    from scenarios.task_medium import generate_medium_scenario
    from scenarios.task_hard import generate_hard_scenario


CORRECT_ACTIONS = {
    "OOM":            ["scale_out", "restart_service"],
    "BAD_DEPLOY":     ["rollback_deploy"],
    "CONFIG_ERROR":   ["fix_config"],
    "DISK_FULL":      ["cleanup_disk"],
    "DB_CONN_LIMIT":  ["increase_db_pool"],
    "RACE_CONDITION": ["fix_config"],
    "NETWORK_TIMEOUT":["increase_timeout"],
}

MAX_STEPS = {"easy": 10, "medium": 18, "hard": 25}
OPTIMAL   = {"easy": 5,  "medium": 9,  "hard": 13}

VALID_TASKS = {"easy", "medium", "hard"}


class IncidentResponseEnvironment:
    """
    Stateful environment for one task (easy / medium / hard).
    Each instance holds exactly one active episode.
    """

    def __init__(self, task_name: str = "easy"):
        if task_name not in VALID_TASKS:
            raise ValueError(f"task_name must be one of {VALID_TASKS}, got {task_name!r}")
        self.task_name = task_name
        self._reset_state()

    # ── Public API ────────────────────────────────────────────────────────────

    def reset(self) -> dict:
        self._reset_state()
        seed = random.randint(0, 99_999)

        generators = {
            "easy":   generate_easy_scenario,
            "medium": generate_medium_scenario,
            "hard":   generate_hard_scenario,
        }
        self.scenario = generators[self.task_name](seed=seed)

        return self._make_obs(0.0, False, "Incident detected. Begin investigation.")

    def step(self, action: dict) -> dict:
        if self.scenario is None:
            return self._make_obs(0.0, False, "Environment not initialized. Call reset() first.")
        if self.done:
            return self._make_obs(0.0, True, "Episode already ended. Call reset() to start a new episode.")

        self.step_count += 1
        reward, query_result, action_result, message = 0.0, None, None, ""

        action_type = action.get("action_type", "")

        # ── query_logs ──────────────────────────────────────────────────────
        if action_type == "query_logs":
            svc = action.get("target_service", "")
            if svc not in self.scenario["logs"]:
                message = f"Unknown service '{svc}'. Available: {list(self.scenario['logs'].keys())}"
            else:
                logs = self.scenario["logs"][svc]
                level = action.get("log_level")
                if level:
                    logs = [l for l in logs if f"[{level.upper()}]" in l]
                query_result = {"service": svc, "logs": logs[:15]}
                self.queried_services.add(svc)
                if svc == self.scenario["affected_service"]:
                    reward += 0.08
                    message = f"Logs retrieved for {svc}. Check for error patterns."
                else:
                    reward -= 0.01
                    message = f"Logs retrieved for {svc}. Service appears healthy."

        # ── query_metrics ───────────────────────────────────────────────────
        elif action_type == "query_metrics":
            svc = action.get("target_service", "")
            if svc not in self.scenario["metrics"]:
                message = f"Unknown service '{svc}'. Available: {list(self.scenario['metrics'].keys())}"
            else:
                query_result = {"service": svc, "metrics": self.scenario["metrics"][svc]}
                if svc == self.scenario["affected_service"]:
                    reward += 0.06
                    message = f"Metrics retrieved for {svc}. Review anomalies carefully."
                else:
                    reward -= 0.01
                    message = f"Metrics for {svc} retrieved. Within normal range."

        # ── query_alerts ────────────────────────────────────────────────────
        elif action_type == "query_alerts":
            query_result = {"alerts": self.scenario["alerts"]}
            reward += 0.03
            message = "Active alerts retrieved."

        # ── query_dependencies (medium task helper) ─────────────────────────
        elif action_type == "query_dependencies":
            dep_map = self.scenario.get("dependency_map")
            if dep_map is None:
                query_result = {"info": "Dependency map not available for this task."}
                message = "No dependency map for this task."
            else:
                svc = action.get("target_service", "")
                deps = dep_map.get(svc)
                if deps is None:
                    query_result = {"info": f"Service '{svc}' not found in dependency map."}
                    message = f"Unknown service '{svc}'."
                else:
                    query_result = {"service": svc, "depends_on": deps}
                    reward += 0.04
                    message = f"Dependencies for {svc} retrieved."

        # ── identify_cause ──────────────────────────────────────────────────
        elif action_type == "identify_cause":
            if self.root_cause_declared:
                reward -= 0.05
                message = "Root cause already declared. Proceed to take_action."
            else:
                self.root_cause_declared = True
                declared_svc   = action.get("suspected_service", "")
                declared_cause = action.get("suspected_cause", "")
                correct_svc    = self.scenario["affected_service"]
                correct_cause  = self.scenario["root_cause"]

                svc_ok   = declared_svc   == correct_svc
                cause_ok = declared_cause == correct_cause

                if svc_ok and cause_ok:
                    self.correct_cause = True
                    reward += 0.30
                    message = f"Correct! Root cause: {correct_cause} on {correct_svc}."
                elif svc_ok:
                    reward += 0.12
                    message = "Service is correct but the cause type is wrong."
                elif cause_ok:
                    reward += 0.10
                    message = "Cause type is correct but the service is wrong."
                else:
                    reward -= 0.10
                    message = "Incorrect diagnosis. Continue investigating."

        # ── take_action ─────────────────────────────────────────────────────
        elif action_type == "take_action":
            mitigation = action.get("mitigation", "")
            allowed    = CORRECT_ACTIONS.get(self.scenario["root_cause"], [])

            if not self.root_cause_declared:
                reward -= 0.05
                message = "Identify the root cause before taking action."
            elif self.mitigation_taken:
                reward -= 0.05
                message = "Mitigation already applied. Use verify_recovery to confirm."
            else:
                self.mitigation_taken = True
                if mitigation in allowed:
                    self.correct_mitigation = True
                    reward += 0.40
                    message = f"Correct mitigation applied: {mitigation}. Service is recovering..."
                elif mitigation == "escalate_to_human":
                    reward += 0.05
                    message = "Escalated to human engineer. Incident handed off."
                    self.done = True
                else:
                    self.wrong_action_count += 1
                    reward -= 0.15
                    message = (
                        f"Wrong mitigation: '{mitigation}'. "
                        f"This may worsen the incident. Consider your diagnosis again."
                    )

        # ── verify_recovery ─────────────────────────────────────────────────
        elif action_type == "verify_recovery":
            if not self.mitigation_taken:
                reward -= 0.03
                message = "No mitigation has been applied yet."
            elif self.correct_mitigation and not self.recovery_verified:
                self.recovery_verified = True
                reward += 0.15
                message = (
                    "Service health confirmed. Error rate back to normal. "
                    "Incident resolved successfully."
                )
                self.done = True
            elif self.recovery_verified:
                reward -= 0.02
                message = "Recovery already verified."
            else:
                reward -= 0.05
                message = "Service is still degraded. The applied mitigation was incorrect."

        else:
            message = (
                f"Unknown action_type: '{action_type}'. "
                "Valid types: query_logs, query_metrics, query_alerts, query_dependencies, "
                "identify_cause, take_action, verify_recovery"
            )

        # ── Per-step efficiency penalty ─────────────────────────────────────
        opt = OPTIMAL.get(self.task_name, 5)
        if self.step_count > opt:
            reward -= 0.02

        # ── Max steps check ─────────────────────────────────────────────────
        if self.step_count >= MAX_STEPS.get(self.task_name, 10):
            self.done = True
            message += " | Max steps reached. Episode ending."

        self.cumulative_reward = min(1.0, max(0.0, self.cumulative_reward + reward))
        return self._make_obs(reward, self.done, message, query_result, action_result)

    def state(self) -> dict:
        return {
            "episode_id":              self.episode_id,
            "task_name":               self.task_name,
            "step_count":              self.step_count,
            "max_steps":               MAX_STEPS.get(self.task_name, 10),
            "done":                    self.done,
            "root_cause_identified":   self.root_cause_declared,
            "correct_cause_identified":self.correct_cause,
            "mitigation_taken":        self.mitigation_taken,
            "correct_mitigation_taken":self.correct_mitigation,
            "recovery_verified":       self.recovery_verified,
            "cumulative_reward":       round(self.cumulative_reward, 3),
            "score":                   round(self._compute_score(), 3),
        }

    # ── Private helpers ───────────────────────────────────────────────────────

    def _reset_state(self):
        self.episode_id          = str(uuid.uuid4())[:8]
        self.step_count          = 0
        self.done                = False
        self.scenario            = None
        self.cumulative_reward   = 0.0
        self.root_cause_declared = False
        self.correct_cause       = False
        self.mitigation_taken    = False
        self.correct_mitigation  = False
        self.recovery_verified   = False
        self.queried_services    = set()
        self.wrong_action_count  = 0

    def _compute_score(self) -> float:
        score = 0.0
        if self.correct_cause:       score += 0.35
        if self.correct_mitigation:  score += 0.40
        if self.recovery_verified:   score += 0.15
        opt = OPTIMAL.get(self.task_name, 5)
        if self.scenario and self.step_count <= opt:
            score += 0.10
        return min(1.0, score)

    def _make_obs(
        self,
        reward: float,
        done: bool,
        message: str,
        query_result: Optional[dict] = None,
        action_result: Optional[str] = None,
    ) -> dict:
        sc = self.scenario or {}
        return {
            "task_name":        sc.get("task_name", self.task_name),
            "task_description": sc.get("task_description", ""),
            "system_overview":  sc.get("system_overview", {}),
            "active_alerts":    sc.get("alerts", []),
            "query_result":     query_result,
            "action_result":    action_result,
            "reward":           round(reward, 3),
            "done":             done,
            "step_count":       self.step_count,
            "message":          message,
        }
