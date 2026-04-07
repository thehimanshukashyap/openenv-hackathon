"""
FastAPI application for the Incident Response Triage Environment.

Endpoints:
  POST /reset?task_name=easy|medium|hard  — start new episode
  POST /step                              — execute one action
  GET  /state?task_name=easy|medium|hard  — get episode state & score
  GET  /health                            — liveness probe

Run locally:
  uvicorn server.app:app --reload --host 0.0.0.0 --port 8000
Or:
  python -m incident_response_env.server.app
"""

import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional

try:
    from server.environment import IncidentResponseEnvironment
except ImportError:
    from environment import IncidentResponseEnvironment


app = FastAPI(
    title="Incident Response Triage Environment",
    description="OpenEnv environment — AI agent investigates and resolves system incidents.",
    version="1.0.0",
)

# One isolated environment instance per task difficulty
_envs: dict[str, IncidentResponseEnvironment] = {
    "easy":   IncidentResponseEnvironment("easy"),
    "medium": IncidentResponseEnvironment("medium"),
    "hard":   IncidentResponseEnvironment("hard"),
}

VALID_TASKS = {"easy", "medium", "hard"}


def _get_env(task_name: str) -> IncidentResponseEnvironment:
    if task_name not in VALID_TASKS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid task_name '{task_name}'. Must be one of: easy, medium, hard",
        )
    return _envs[task_name]


# ── Request model ─────────────────────────────────────────────────────────────

class ActionRequest(BaseModel):
    action_type: str
    target_service: Optional[str] = None
    log_level: Optional[str] = None
    suspected_service: Optional[str] = None
    suspected_cause: Optional[str] = None
    mitigation: Optional[str] = None
    task_name: str = "easy"


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.post("/reset")
def reset(task_name: str = "easy"):
    """Reset the environment and start a new episode for the given task."""
    env = _get_env(task_name)
    return env.reset()


@app.post("/step")
def step(request: ActionRequest):
    """Execute one action in the current episode."""
    env = _get_env(request.task_name)
    return env.step(request.model_dump())


@app.get("/state")
def state(task_name: str = "easy"):
    """Return the current episode state and running score."""
    env = _get_env(task_name)
    return env.state()


@app.get("/health")
def health():
    """Liveness probe."""
    return {"status": "ok", "tasks": list(VALID_TASKS)}


@app.get("/schema")
def schema():
    """Return action/observation schemas."""
    return {
        "action_types": [
            "query_logs", "query_metrics", "query_alerts", "query_dependencies",
            "identify_cause", "take_action", "verify_recovery",
        ],
        "mitigations": [
            "restart_service", "rollback_deploy", "fix_config",
            "scale_out", "cleanup_disk", "increase_db_pool",
            "flush_cache", "escalate_to_human", "increase_timeout",
        ],
        "root_causes": [
            "OOM", "BAD_DEPLOY", "CONFIG_ERROR", "DISK_FULL",
            "DB_CONN_LIMIT", "RACE_CONDITION",
        ],
        "services": [
            "api-gateway", "auth-service", "payment-service",
            "user-service", "cache-service", "db-primary", "notification-svc",
        ],
    }


# ── Entry point for direct execution ─────────────────────────────────────────

def main(host: str = "0.0.0.0", port: int = 8000):
    import uvicorn
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=int(os.getenv("PORT", 8000)))
    parser.add_argument("--host", type=str, default="0.0.0.0")
    args = parser.parse_args()
    main(host=args.host, port=args.port)
