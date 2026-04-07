"""
TASK 2 — MEDIUM
Cascading failure. api-gateway → user-service → db-primary.
db-primary is always the root cause. api-gateway shows the most errors (red herring).
Agent must trace the dependency chain to find the real root service.
Optimal path: 6–10 steps. Max steps: 18.
"""

import random
from .generator import SERVICES, generate_normal_log, generate_error_log, generate_metrics, generate_alert

MEDIUM_CAUSES = ["DB_CONN_LIMIT", "CONFIG_ERROR", "OOM"]

# Fixed dependency chain: api-gateway depends on user-service depends on db-primary
CHAIN = ["api-gateway", "user-service", "db-primary"]

DEPENDENCY_MAP = {
    "api-gateway":    ["user-service", "payment-service", "auth-service"],
    "auth-service":   ["db-primary", "cache-service"],
    "payment-service":["db-primary"],
    "user-service":   ["db-primary", "cache-service"],
    "cache-service":  [],
    "db-primary":     [],
    "notification-svc": [],
}


def generate_medium_scenario(seed: int = None) -> dict:
    if seed is not None:
        random.seed(seed)

    root_cause = random.choice(MEDIUM_CAUSES)
    top_service, mid_service, root_service = CHAIN  # api-gateway, user-service, db-primary

    logs = {}
    for svc in SERVICES:
        if svc == top_service:
            # Most visible errors — but caused by upstream dependency
            lines = [generate_normal_log(svc) for _ in range(10)]
            lines += [
                f"[ERROR] Connection to {mid_service} timed out after 30s",
                f"[ERROR] Upstream dependency {mid_service} returned 503",
                f"[WARN]  Circuit breaker OPEN for {mid_service}",
                f"[ERROR] Request failed: dependency unavailable",
            ] * 3
        elif svc == mid_service:
            # Secondary errors — also a downstream victim
            lines = [generate_normal_log(svc) for _ in range(12)]
            lines += [
                f"[ERROR] Cannot connect to {root_service}: connection refused",
                f"[WARN]  {root_service} query taking >5000ms",
                generate_error_log(svc, root_cause),
            ] * 2
        elif svc == root_service:
            # Root cause — fewer visible alerts but these are the real ones
            lines = [generate_normal_log(svc) for _ in range(18)]
            lines += [generate_error_log(svc, root_cause) for _ in range(5)]
        else:
            lines = [generate_normal_log(svc) for _ in range(20)]
        logs[svc] = lines

    metrics = {}
    for svc in SERVICES:
        if svc == top_service:
            metrics[svc] = {
                "cpu_percent": 45, "memory_percent": 55,
                "error_rate": 75, "latency_p99_ms": 5000, "request_rate": 20,
            }
        elif svc == mid_service:
            metrics[svc] = {
                "cpu_percent": 30, "memory_percent": 40,
                "error_rate": 60, "latency_p99_ms": 3000, "request_rate": 15,
            }
        elif svc == root_service:
            metrics[svc] = generate_metrics(svc, root_cause, is_affected=True)
        else:
            metrics[svc] = generate_metrics(svc, root_cause, is_affected=False)

    alerts = [
        generate_alert(top_service,  "BAD_DEPLOY", "CRITICAL"),  # misleading — most alarming
        generate_alert(mid_service,  "BAD_DEPLOY", "HIGH"),
        generate_alert(root_service, root_cause,   "HIGH"),       # real cause (less obvious)
    ]

    system_overview = {
        svc: {
            "status": "DEGRADED" if svc in CHAIN else "HEALTHY",
            "error_rate": metrics[svc]["error_rate"],
        }
        for svc in SERVICES
    }

    return {
        "task_name": "medium",
        "affected_service": root_service,
        "root_cause": root_cause,
        "dependency_chain": CHAIN,
        "dependency_map": DEPENDENCY_MAP,
        "logs": logs,
        "metrics": metrics,
        "alerts": alerts,
        "system_overview": system_overview,
        "task_description": (
            "INCIDENT ACTIVE: Multiple services are degraded. "
            "Services have dependencies — an upstream failure cascades downstream. "
            "Find the ROOT CAUSE service (not the symptom), identify the cause, "
            "and apply the correct fix. Fixing a symptom without fixing the root will not resolve the incident."
        ),
    }
