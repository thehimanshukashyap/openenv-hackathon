"""
TASK 3 — HARD
Intermittent race condition on cache-service. All metrics look normal.
No alert fires on cache-service — agent must discover it independently.
Red herring alerts on payment-service and user-service.
Optimal path: 10–15 steps. Max steps: 25.
"""

import random
from .generator import SERVICES, generate_normal_log, generate_error_log, generate_alert


def generate_hard_scenario(seed: int = None) -> dict:
    if seed is not None:
        random.seed(seed)

    root_cause = "RACE_CONDITION"
    affected = "cache-service"

    logs = {}
    for svc in SERVICES:
        lines = [generate_normal_log(svc) for _ in range(20)]
        if svc == affected:
            # Intermittent — mostly normal, occasional race-condition errors
            lines += [generate_error_log(svc, root_cause) for _ in range(4)]
            lines += [
                "[WARN]  Cache eviction rate elevated: 12% above baseline",
                "[INFO]  Concurrent write count: 847 (threshold: 800)",
                "[WARN]  Write lock contention detected on key prefix 'sess_'",
            ]
        elif svc == "payment-service":
            # Red herring — shows errors but is a victim of stale cache reads
            lines += [
                "[ERROR] Stale session data returned for user checkout",
                "[WARN]  Payment idempotency check failed — possible duplicate",
            ]
        elif svc == "user-service":
            # Red herring — slightly elevated latency, looks suspicious
            lines += [
                "[WARN]  Slow response from cache-service: 340ms (baseline 20ms)",
                "[INFO]  Retrying cache read after empty response",
            ]
        logs[svc] = lines

    # All metrics look NORMAL — this is the trap
    metrics = {}
    for svc in SERVICES:
        metrics[svc] = {
            "cpu_percent": round(random.uniform(15, 45), 1),
            "memory_percent": round(random.uniform(25, 55), 1),
            "error_rate": round(random.uniform(1, 8), 2),   # low — not alarming
            "latency_p99_ms": random.randint(80, 250),       # looks fine
            "request_rate": random.randint(100, 400),
        }

    # Special hidden metrics on cache-service — only visible if agent queries it directly
    metrics[affected]["concurrent_writes"] = 847
    metrics[affected]["write_lock_wait_ms"] = 340
    metrics[affected]["cache_hit_rate"] = 0.61          # should be >0.90

    alerts = [
        generate_alert("payment-service", "BAD_DEPLOY", "HIGH"),    # red herring
        generate_alert("user-service",    "BAD_DEPLOY", "MEDIUM"),  # red herring
        # Intentionally NO alert for cache-service
    ]

    system_overview = {
        svc: {
            "status": "DEGRADED" if svc in ("payment-service", "user-service") else "HEALTHY",
            "error_rate": metrics[svc]["error_rate"],
        }
        for svc in SERVICES
    }

    return {
        "task_name": "hard",
        "affected_service": affected,
        "root_cause": root_cause,
        "logs": logs,
        "metrics": metrics,
        "alerts": alerts,
        "system_overview": system_overview,
        "task_description": (
            "INCIDENT ACTIVE: Users are reporting intermittent failures (~30% of requests). "
            "All services appear healthy on the surface. Standard metrics look normal. "
            "Investigate carefully — the root cause is subtle. "
            "Identify the real affected service and root cause before taking action."
        ),
    }
