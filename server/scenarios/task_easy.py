"""
TASK 1 — EASY
Single service incident. Root cause is clearly visible in logs.
Optimal path: query_logs → identify_cause → take_action → verify_recovery (4–6 steps)
Max steps: 10
"""

import random
from .generator import SERVICES, generate_normal_log, generate_error_log, generate_metrics, generate_alert

EASY_CAUSES = ["OOM", "BAD_DEPLOY", "CONFIG_ERROR", "DISK_FULL", "DB_CONN_LIMIT"]


def generate_easy_scenario(seed: int = None) -> dict:
    if seed is not None:
        random.seed(seed)

    affected_service = random.choice(SERVICES)
    root_cause = random.choice(EASY_CAUSES)

    # Build log store — mix of normal + obvious error logs for affected service
    logs = {}
    for svc in SERVICES:
        if svc == affected_service:
            lines = [generate_normal_log(svc) for _ in range(15)]
            lines += [generate_error_log(svc, root_cause) for _ in range(8)]
            random.shuffle(lines)
        else:
            lines = [generate_normal_log(svc) for _ in range(20)]
        logs[svc] = lines  # newest first would require sorting; keep shuffled for realism

    metrics = {
        svc: generate_metrics(svc, root_cause, is_affected=(svc == affected_service))
        for svc in SERVICES
    }

    alerts = [generate_alert(affected_service, root_cause, "CRITICAL")]

    system_overview = {
        svc: {
            "status": "DEGRADED" if svc == affected_service else "HEALTHY",
            "error_rate": metrics[svc]["error_rate"],
        }
        for svc in SERVICES
    }

    return {
        "task_name": "easy",
        "affected_service": affected_service,
        "root_cause": root_cause,
        "logs": logs,
        "metrics": metrics,
        "alerts": alerts,
        "system_overview": system_overview,
        "task_description": (
            "INCIDENT ACTIVE: One or more services are degraded. "
            "Investigate, identify the root cause, and apply the correct mitigation. "
            "You have access to logs, metrics, and alerts for all services."
        ),
    }
