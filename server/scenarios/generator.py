"""
Core data-generation utilities shared by all task scenarios.
Generates realistic-looking but entirely synthetic logs, metrics, and alerts.
"""

import random
from faker import Faker
from datetime import datetime, timedelta

fake = Faker()

SERVICES = [
    "api-gateway",
    "auth-service",
    "payment-service",
    "user-service",
    "cache-service",
    "db-primary",
    "notification-svc",
]

ROOT_CAUSES = ["OOM", "BAD_DEPLOY", "CONFIG_ERROR", "DISK_FULL", "DB_CONN_LIMIT", "RACE_CONDITION"]


def random_timestamp(minutes_ago_max: int = 60) -> str:
    delta = random.randint(0, minutes_ago_max)
    t = datetime.now() - timedelta(minutes=delta)
    return t.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


def generate_normal_log(service: str) -> str:
    templates = [
        f"[INFO]  {random_timestamp()} {service} - Request processed in {random.randint(12, 89)}ms",
        f"[INFO]  {random_timestamp()} {service} - Health check passed",
        f"[DEBUG] {random_timestamp()} {service} - Cache hit ratio: {random.uniform(0.85, 0.99):.2f}",
        f"[INFO]  {random_timestamp()} {service} - {random.randint(10, 200)} concurrent connections",
        f"[INFO]  {random_timestamp()} {service} - Processed {random.randint(5, 50)} requests in last 10s",
    ]
    return random.choice(templates)


def generate_error_log(service: str, cause: str) -> str:
    log_templates = {
        "OOM": [
            f"[ERROR] {random_timestamp()} {service} - java.lang.OutOfMemoryError: GC overhead limit exceeded",
            f"[ERROR] {random_timestamp()} {service} - Container killed: OOM. Memory usage: 7.8Gi/8Gi",
            f"[WARN]  {random_timestamp()} {service} - Heap usage at 94%. GC running continuously.",
            f"[ERROR] {random_timestamp()} {service} - java.lang.OutOfMemoryError: Java heap space",
        ],
        "BAD_DEPLOY": [
            f"[ERROR] {random_timestamp()} {service} - AttributeError: 'NoneType' object has no attribute 'user_id'",
            f"[ERROR] {random_timestamp()} {service} - KeyError: 'payment_method' missing in request payload",
            f"[ERROR] {random_timestamp()} {service} - Traceback: deploy v2.4.1 introduced breaking change in /checkout",
            f"[ERROR] {random_timestamp()} {service} - Application startup failed: Exit code 1",
        ],
        "CONFIG_ERROR": [
            f"[ERROR] {random_timestamp()} {service} - DB_HOST env var not set. Connection refused.",
            f"[ERROR] {random_timestamp()} {service} - SSL_CERT_PATH points to non-existent file: /certs/prod.pem",
            f"[WARN]  {random_timestamp()} {service} - TIMEOUT_MS=0 detected. Using default 30000ms.",
            f"[ERROR] {random_timestamp()} {service} - NullPointerException: SMTP_HOST environment variable is null",
        ],
        "DISK_FULL": [
            f"[ERROR] {random_timestamp()} {service} - OSError: [Errno 28] No space left on device",
            f"[ERROR] {random_timestamp()} {service} - Failed to write log file. Disk usage: 100%",
            f"[WARN]  {random_timestamp()} {service} - /var/log partition at 98%. Rotation failed.",
            f"[ERROR] {random_timestamp()} {service} - IOError: disk quota exceeded while writing to /data",
        ],
        "DB_CONN_LIMIT": [
            f"[ERROR] {random_timestamp()} {service} - FATAL: remaining connection slots reserved for replication",
            f"[ERROR] {random_timestamp()} {service} - psycopg2.OperationalError: FATAL: too many connections",
            f"[WARN]  {random_timestamp()} {service} - Connection pool exhausted. Waiting for available slot...",
            f"[ERROR] {random_timestamp()} {service} - HikariPool: Connection is not available, request timed out after 30000ms",
        ],
        "RACE_CONDITION": [
            f"[ERROR] {random_timestamp()} {service} - Concurrent write conflict on session_id='{fake.uuid4()[:8]}'",
            f"[WARN]  {random_timestamp()} {service} - Stale read detected. Data version mismatch.",
            f"[ERROR] {random_timestamp()} {service} - DeadlockException: Transaction aborted after 3 retries",
            f"[WARN]  {random_timestamp()} {service} - Optimistic lock failed on key — concurrent write detected",
        ],
    }
    return random.choice(log_templates.get(cause, log_templates["BAD_DEPLOY"]))


def generate_metrics(service: str, cause: str, is_affected: bool = True) -> dict:
    if not is_affected:
        return {
            "cpu_percent": round(random.uniform(10, 35), 1),
            "memory_percent": round(random.uniform(20, 50), 1),
            "error_rate": round(random.uniform(0.0, 0.5), 2),
            "latency_p99_ms": random.randint(45, 150),
            "request_rate": random.randint(80, 300),
        }
    profiles = {
        "OOM":           {"cpu": (70, 95), "mem": (90, 99), "err": (15, 40), "lat": (800, 3000)},
        "BAD_DEPLOY":    {"cpu": (30, 60), "mem": (40, 65), "err": (20, 60), "lat": (200, 800)},
        "CONFIG_ERROR":  {"cpu": (5, 20),  "mem": (30, 50), "err": (80, 100), "lat": (2000, 5000)},
        "DISK_FULL":     {"cpu": (40, 70), "mem": (50, 70), "err": (10, 30), "lat": (500, 1500)},
        "DB_CONN_LIMIT": {"cpu": (20, 40), "mem": (30, 55), "err": (30, 70), "lat": (1000, 4000)},
        "RACE_CONDITION":{"cpu": (25, 45), "mem": (35, 60), "err": (5, 20),  "lat": (100, 300)},
    }
    p = profiles.get(cause, profiles["BAD_DEPLOY"])
    return {
        "cpu_percent": round(random.uniform(*p["cpu"]), 1),
        "memory_percent": round(random.uniform(*p["mem"]), 1),
        "error_rate": round(random.uniform(*p["err"]), 2),
        "latency_p99_ms": random.randint(*p["lat"]),
        "request_rate": random.randint(10, 80),
    }


def generate_alert(service: str, cause: str, severity: str = "CRITICAL") -> dict:
    alert_templates = {
        "OOM":           f"OOMKillDetected: {service} container killed due to memory exhaustion",
        "BAD_DEPLOY":    f"HighErrorRate: {service} error rate {random.randint(20, 60)}% above threshold",
        "CONFIG_ERROR":  f"ServiceUnreachable: {service} failing all health checks for {random.randint(3, 12)}min",
        "DISK_FULL":     f"DiskSpaceCritical: {service} host disk usage >95%",
        "DB_CONN_LIMIT": f"DatabaseConnectionPoolExhausted: {service} cannot acquire DB connection",
        "RACE_CONDITION":f"DataConsistencyWarning: {service} reporting intermittent write conflicts",
    }
    return {
        "alert_name": alert_templates.get(cause, f"ServiceDegraded: {service}"),
        "service": service,
        "severity": severity,
        "fired_at": random_timestamp(5),
        "runbook": f"https://runbooks.internal/{service.replace('-', '_')}_incidents",
    }
