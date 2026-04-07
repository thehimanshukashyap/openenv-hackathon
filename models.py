"""Data models for the Incident Response Triage Environment."""

from pydantic import BaseModel
from typing import Optional, List, Dict, Any


class IncidentAction(BaseModel):
    action_type: str
    # query_logs / query_metrics
    target_service: Optional[str] = None
    log_level: Optional[str] = None        # ERROR / WARN / INFO
    # identify_cause
    suspected_service: Optional[str] = None
    suspected_cause: Optional[str] = None
    # take_action
    mitigation: Optional[str] = None
    # which task to act on
    task_name: str = "easy"


class IncidentObservation(BaseModel):
    task_name: str
    task_description: str
    system_overview: Dict[str, Any]
    active_alerts: List[Dict[str, Any]]
    query_result: Optional[Dict[str, Any]] = None
    action_result: Optional[str] = None
    reward: float
    done: bool
    step_count: int
    message: str


class IncidentState(BaseModel):
    episode_id: str
    task_name: str
    step_count: int
    max_steps: int
    done: bool
    root_cause_identified: bool
    correct_cause_identified: bool
    mitigation_taken: bool
    correct_mitigation_taken: bool
    recovery_verified: bool
    cumulative_reward: float
    score: float  # final 0.0–1.0


# ── Backward-compat aliases (old echo env) ──────────────────────────────────
# Kept so existing __init__.py exports don't break during transition.
IncidentResponseAction = IncidentAction
IncidentResponseObservation = IncidentObservation
