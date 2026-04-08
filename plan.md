# Incident Response Triage — OpenEnv Hackathon
Team Gutka | Deadline: April 8, 11:59 PM

---

## What You're Building
An OpenEnv env that simulates an on-call war room. Agent receives alerts, queries logs/metrics, traces dependencies, identifies root cause, takes mitigation action. Grader scores performance.

**Flow:** `reset()` → agent queries → agent acts → `state()` scores

---

## Final File Structure

```
incident_response_env/
├── inference.py          ← ROOT LEVEL, exact name mandatory
├── README.md
├── openenv.yaml
├── pyproject.toml
├── __init__.py
├── models.py
├── client.py
└── server/
    ├── app.py
    ├── environment.py
    ├── requirements.txt
    ├── Dockerfile
    └── scenarios/
        ├── __init__.py
        ├── generator.py
        ├── task_easy.py
        ├── task_medium.py
        └── task_hard.py
```

---

## Phase 0 — Setup

```bash
pip install openenv-core fastapi uvicorn pydantic faker numpy python-dotenv openai
openenv init incident_response_env
cd incident_response_env
mkdir server/scenarios && touch server/scenarios/__init__.py
touch server/scenarios/generator.py server/scenarios/task_easy.py
touch server/scenarios/task_medium.py server/scenarios/task_hard.py
touch inference.py
```

**.env** (never commit):
```
API_BASE_URL=https://router.huggingface.co/v1
MODEL_NAME=Qwen/Qwen2.5-72B-Instruct
HF_TOKEN=hf_your_token_here
```

---

## Phase 1 — World Design

**Services:** `api-gateway`, `auth-service`, `payment-service`, `user-service`, `cache-service`, `db-primary`, `notification-svc`

**Root causes:**
```python
CORRECT_ACTIONS = {
    'OOM'           : ['scale_out', 'restart_service'],
    'BAD_DEPLOY'    : ['rollback_deploy'],
    'CONFIG_ERROR'  : ['fix_config'],
    'DISK_FULL'     : ['cleanup_disk'],
    'DB_CONN_LIMIT' : ['increase_db_pool'],
    'RACE_CONDITION': ['fix_config'],
    'NETWORK_TIMEOUT':['increase_timeout'],
}
```

**Agent actions:** `query_logs`, `query_metrics`, `query_alerts`, `identify_cause`, `take_action`, `verify_recovery`

**Mitigations:** `restart_service`, `rollback_deploy`, `fix_config`, `scale_out`, `cleanup_disk`, `increase_db_pool`, `flush_cache`, `escalate_to_human`, `increase_timeout`

---

## Phase 2 — models.py

```python
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

class IncidentAction(BaseModel):
    action_type: str
    target_service: Optional[str] = None
    metric_name: Optional[str] = None
    time_range_minutes: Optional[int] = 10
    log_level: Optional[str] = None        # ERROR / WARN / INFO
    suspected_service: Optional[str] = None
    suspected_cause: Optional[str] = None
    mitigation: Optional[str] = None
    verify_service: Optional[str] = None

class IncidentObservation(BaseModel):
    task_name: str
    task_description: str
    system_overview: Dict[str, Any]
    active_alerts: List[Dict[str, Any]]
    query_result: Optional[Dict[str, Any]]
    action_result: Optional[str]
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
    score: float   # final 0.0–1.0
```

---

## Phase 3 — Scenario Generator

### server/scenarios/generator.py

```python
import random
from faker import Faker
from datetime import datetime, timedelta

fake = Faker()
SERVICES = ['api-gateway','auth-service','payment-service',
            'user-service','cache-service','db-primary','notification-svc']

def random_timestamp(minutes_ago_max=60):
    delta = random.randint(0, minutes_ago_max)
    t = datetime.now() - timedelta(minutes=delta)
    return t.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]

def generate_normal_log(service):
    templates = [
        f"[INFO]  {random_timestamp()} {service} - Request processed in {random.randint(12,89)}ms",
        f"[INFO]  {random_timestamp()} {service} - Health check passed",
        f"[DEBUG] {random_timestamp()} {service} - Cache hit ratio: {random.uniform(0.85,0.99):.2f}",
        f"[INFO]  {random_timestamp()} {service} - {random.randint(10,200)} concurrent connections",
    ]
    return random.choice(templates)

def generate_error_log(service, cause):
    log_templates = {
        'OOM': [
            f"[ERROR] {random_timestamp()} {service} - java.lang.OutOfMemoryError: GC overhead limit exceeded",
            f"[ERROR] {random_timestamp()} {service} - Container killed: OOM. Memory usage: 7.8Gi/8Gi",
            f"[WARN]  {random_timestamp()} {service} - Heap usage at 94%. GC running continuously.",
        ],
        'BAD_DEPLOY': [
            f"[ERROR] {random_timestamp()} {service} - AttributeError: 'NoneType' object has no attribute 'user_id'",
            f"[ERROR] {random_timestamp()} {service} - KeyError: 'payment_method' missing in request payload",
            f"[ERROR] {random_timestamp()} {service} - Traceback: deploy v2.4.1 introduced breaking change in /checkout",
        ],
        'CONFIG_ERROR': [
            f"[ERROR] {random_timestamp()} {service} - DB_HOST env var not set. Connection refused.",
            f"[ERROR] {random_timestamp()} {service} - SSL_CERT_PATH points to non-existent file: /certs/prod.pem",
            f"[WARN]  {random_timestamp()} {service} - TIMEOUT_MS=0 detected. Using default 30000ms.",
        ],
        'DISK_FULL': [
            f"[ERROR] {random_timestamp()} {service} - OSError: [Errno 28] No space left on device",
            f"[ERROR] {random_timestamp()} {service} - Failed to write log file. Disk usage: 100%",
            f"[WARN]  {random_timestamp()} {service} - /var/log partition at 98%. Rotation failed.",
        ],
        'DB_CONN_LIMIT': [
            f"[ERROR] {random_timestamp()} {service} - FATAL: remaining connection slots reserved for replication",
            f"[ERROR] {random_timestamp()} {service} - psycopg2.OperationalError: FATAL: too many connections",
            f"[WARN]  {random_timestamp()} {service} - Connection pool exhausted. Waiting for available slot...",
        ],
        'RACE_CONDITION': [
            f"[ERROR] {random_timestamp()} {service} - Concurrent write conflict on session_id='{fake.uuid4()[:8]}'",
            f"[WARN]  {random_timestamp()} {service} - Stale read detected. Data version mismatch.",
            f"[ERROR] {random_timestamp()} {service} - DeadlockException: Transaction aborted after 3 retries",
        ],
    }
    return random.choice(log_templates.get(cause, log_templates['BAD_DEPLOY']))

def generate_metrics(service, cause, is_affected=True):
    if not is_affected:
        return {'cpu_percent': round(random.uniform(10,35),1),
                'memory_percent': round(random.uniform(20,50),1),
                'error_rate': round(random.uniform(0.0,0.5),2),
                'latency_p99_ms': random.randint(45,150),
                'request_rate': random.randint(80,300)}
    profiles = {
        'OOM'          : {'cpu':(70,95),'mem':(90,99),'err':(15,40),'lat':(800,3000)},
        'BAD_DEPLOY'   : {'cpu':(30,60),'mem':(40,65),'err':(20,60),'lat':(200,800)},
        'CONFIG_ERROR' : {'cpu':(5,20), 'mem':(30,50),'err':(80,100),'lat':(2000,5000)},
        'DISK_FULL'    : {'cpu':(40,70),'mem':(50,70),'err':(10,30),'lat':(500,1500)},
        'DB_CONN_LIMIT': {'cpu':(20,40),'mem':(30,55),'err':(30,70),'lat':(1000,4000)},
        'RACE_CONDITION':{'cpu':(25,45),'mem':(35,60),'err':(5,20), 'lat':(100,300)},
    }
    p = profiles.get(cause, profiles['BAD_DEPLOY'])
    return {'cpu_percent': round(random.uniform(*p['cpu']),1),
            'memory_percent': round(random.uniform(*p['mem']),1),
            'error_rate': round(random.uniform(*p['err']),2),
            'latency_p99_ms': random.randint(*p['lat']),
            'request_rate': random.randint(10,80)}

def generate_alert(service, cause, severity='CRITICAL'):
    alert_templates = {
        'OOM'          : f"OOMKillDetected: {service} container killed due to memory exhaustion",
        'BAD_DEPLOY'   : f"HighErrorRate: {service} error rate {random.randint(20,60)}% above threshold",
        'CONFIG_ERROR' : f"ServiceUnreachable: {service} failing all health checks for {random.randint(3,12)}min",
        'DISK_FULL'    : f"DiskSpaceCritical: {service} host disk usage >95%",
        'DB_CONN_LIMIT': f"DatabaseConnectionPoolExhausted: {service} cannot acquire DB connection",
        'RACE_CONDITION':f"DataConsistencyWarning: {service} reporting intermittent write conflicts",
    }
    return {'alert_name': alert_templates.get(cause, f"ServiceDegraded: {service}"),
            'service': service, 'severity': severity,
            'fired_at': random_timestamp(5),
            'runbook': f"https://runbooks.internal/{service.replace('-','_')}_incidents"}
```

### server/scenarios/task_easy.py
Single service, obvious root cause. Optimal: 4–6 steps. Max: 10.

```python
import random
from .generator import SERVICES, generate_normal_log, generate_error_log, generate_metrics, generate_alert

EASY_CAUSES = ['OOM', 'BAD_DEPLOY', 'CONFIG_ERROR', 'DISK_FULL', 'DB_CONN_LIMIT']

def generate_easy_scenario(seed=None):
    if seed: random.seed(seed)
    affected_service = random.choice(SERVICES)
    root_cause = random.choice(EASY_CAUSES)

    logs = {}
    for svc in SERVICES:
        if svc == affected_service:
            lines = [generate_normal_log(svc) for _ in range(15)]
            lines += [generate_error_log(svc, root_cause) for _ in range(8)]
            random.shuffle(lines)
        else:
            lines = [generate_normal_log(svc) for _ in range(20)]
        logs[svc] = sorted(lines, reverse=True)

    metrics = {svc: generate_metrics(svc, root_cause, is_affected=(svc==affected_service))
               for svc in SERVICES}
    alerts = [generate_alert(affected_service, root_cause, 'CRITICAL')]
    system_overview = {svc: {'status': 'DEGRADED' if svc==affected_service else 'HEALTHY',
                              'error_rate': metrics[svc]['error_rate']}
                       for svc in SERVICES}
    return {
        'task_name': 'easy', 'affected_service': affected_service,
        'root_cause': root_cause, 'logs': logs, 'metrics': metrics,
        'alerts': alerts, 'system_overview': system_overview,
        'task_description': ("INCIDENT ACTIVE: One or more services are degraded. "
            "Investigate, identify the root cause, and apply the correct mitigation. "
            "You have access to logs, metrics, and alerts for all services."),
    }
```

### server/scenarios/task_medium.py
Cascading failure. api-gateway → user-service → db-primary. db-primary is always root. Optimal: 6–10 steps. Max: 18.

```python
import random
from .generator import SERVICES, generate_normal_log, generate_error_log, generate_metrics, generate_alert

MEDIUM_CAUSES = ['DB_CONN_LIMIT', 'CONFIG_ERROR', 'OOM']
CHAIN = ['api-gateway', 'user-service', 'db-primary']

def generate_medium_scenario(seed=None):
    if seed: random.seed(seed)
    root_cause = random.choice(MEDIUM_CAUSES)
    top_service, mid_service, root_service = CHAIN

    logs = {}
    for svc in SERVICES:
        if svc == top_service:
            lines = [generate_normal_log(svc) for _ in range(10)]
            lines += [f"[ERROR] Connection to {mid_service} timed out after 30s",
                      f"[ERROR] Upstream dependency {mid_service} returned 503",
                      f"[WARN]  Circuit breaker OPEN for {mid_service}",
                      f"[ERROR] Request failed: dependency unavailable"] * 3
        elif svc == mid_service:
            lines = [generate_normal_log(svc) for _ in range(12)]
            lines += [f"[ERROR] Cannot connect to {root_service}: connection refused",
                      f"[WARN]  {root_service} query taking >5000ms",
                      generate_error_log(svc, root_cause)] * 2
        elif svc == root_service:
            lines = [generate_normal_log(svc) for _ in range(18)]
            lines += [generate_error_log(svc, root_cause) for _ in range(5)]
        else:
            lines = [generate_normal_log(svc) for _ in range(20)]
        logs[svc] = lines

    metrics = {}
    for svc in SERVICES:
        if svc == top_service:
            metrics[svc] = {'cpu_percent':45,'memory_percent':55,'error_rate':75,'latency_p99_ms':5000,'request_rate':20}
        elif svc == mid_service:
            metrics[svc] = {'cpu_percent':30,'memory_percent':40,'error_rate':60,'latency_p99_ms':3000,'request_rate':15}
        elif svc == root_service:
            metrics[svc] = generate_metrics(svc, root_cause, is_affected=True)
        else:
            metrics[svc] = generate_metrics(svc, root_cause, is_affected=False)

    alerts = [
        generate_alert(top_service,  'BAD_DEPLOY', 'CRITICAL'),  # misleading
        generate_alert(mid_service,  'BAD_DEPLOY', 'HIGH'),
        generate_alert(root_service, root_cause,   'HIGH'),       # real one
    ]
    system_overview = {svc: {'status': 'DEGRADED' if svc in CHAIN else 'HEALTHY',
                              'error_rate': metrics[svc]['error_rate']}
                       for svc in SERVICES}
    return {
        'task_name': 'medium', 'affected_service': root_service,
        'root_cause': root_cause, 'dependency_chain': CHAIN,
        'logs': logs, 'metrics': metrics, 'alerts': alerts,
        'system_overview': system_overview,
        'task_description': ("INCIDENT ACTIVE: Multiple services are degraded. "
            "Services have dependencies — an upstream failure can cascade downstream. "
            "Find the ROOT CAUSE service (not the symptom), identify the cause, "
            "and apply the correct fix."),
    }
```

### server/scenarios/task_hard.py
Intermittent race condition. Metrics look normal. No alert on cache-service. Optimal: 10–15 steps. Max: 25.

```python
import random
from .generator import SERVICES, generate_normal_log, generate_error_log, generate_metrics, generate_alert

def generate_hard_scenario(seed=None):
    if seed: random.seed(seed)
    root_cause, affected = 'RACE_CONDITION', 'cache-service'

    logs = {}
    for svc in SERVICES:
        lines = [generate_normal_log(svc) for _ in range(20)]
        if svc == affected:
            lines += [generate_error_log(svc, root_cause) for _ in range(4)]
            lines += ["[WARN]  Cache eviction rate elevated: 12% above baseline",
                      "[INFO]  Concurrent write count: 847 (threshold: 800)",
                      "[WARN]  Write lock contention detected on key prefix 'sess_'"]
        elif svc == 'payment-service':  # red herring
            lines += ["[ERROR] Stale session data returned for user checkout",
                      "[WARN]  Payment idempotency check failed — possible duplicate"]
        logs[svc] = lines

    # All metrics look NORMAL — this is the trap
    metrics = {svc: {'cpu_percent': round(random.uniform(15,45),1),
                     'memory_percent': round(random.uniform(25,55),1),
                     'error_rate': round(random.uniform(1,8),2),
                     'latency_p99_ms': random.randint(80,250),
                     'request_rate': random.randint(100,400)}
               for svc in SERVICES}
    # Hidden metrics — only visible if agent queries cache-service
    metrics[affected]['concurrent_writes'] = 847
    metrics[affected]['write_lock_wait_ms'] = 340
    metrics[affected]['cache_hit_rate'] = 0.61  # should be >0.90

    alerts = [
        generate_alert('payment-service', 'BAD_DEPLOY', 'HIGH'),   # red herring
        generate_alert('user-service',    'BAD_DEPLOY', 'MEDIUM'),  # red herring
        # NO alert for cache-service — agent must discover it
    ]
    system_overview = {svc: {'status': 'DEGRADED' if svc in ['payment-service','user-service'] else 'HEALTHY',
                              'error_rate': metrics[svc]['error_rate']}
                       for svc in SERVICES}
    return {
        'task_name': 'hard', 'affected_service': affected,
        'root_cause': root_cause, 'logs': logs, 'metrics': metrics,
        'alerts': alerts, 'system_overview': system_overview,
        'task_description': ("INCIDENT ACTIVE: Users reporting intermittent failures (~30% of requests). "
            "All services appear healthy on the surface. Standard metrics look normal. "
            "Investigate carefully — the root cause is subtle."),
    }
```

---

## Phase 4 — server/environment.py

```python
import uuid, random
from typing import Optional
from scenarios.task_easy   import generate_easy_scenario
from scenarios.task_medium import generate_medium_scenario
from scenarios.task_hard   import generate_hard_scenario

CORRECT_ACTIONS = {
    'OOM'           : ['scale_out', 'restart_service'],
    'BAD_DEPLOY'    : ['rollback_deploy'],
    'CONFIG_ERROR'  : ['fix_config'],
    'DISK_FULL'     : ['cleanup_disk'],
    'DB_CONN_LIMIT' : ['increase_db_pool'],
    'RACE_CONDITION': ['fix_config'],
    'NETWORK_TIMEOUT':['increase_timeout'],
}
MAX_STEPS  = {'easy': 10, 'medium': 18, 'hard': 25}
OPTIMAL    = {'easy': 5,  'medium': 9,  'hard': 13}

class IncidentResponseEnvironment:

    def __init__(self, task_name: str = 'easy'):
        self.task_name = task_name
        self._reset_state()

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

    def reset(self) -> dict:
        self._reset_state()
        seed = random.randint(0, 99999)
        generators = {'easy': generate_easy_scenario,
                      'medium': generate_medium_scenario,
                      'hard': generate_hard_scenario}
        self.scenario = generators[self.task_name](seed)
        return self._make_obs(0.0, False, "Incident detected. Begin investigation.")

    def step(self, action: dict) -> dict:
        if self.done:
            return self._make_obs(0.0, True, "Episode already ended.")

        self.step_count += 1
        reward, query_result, action_result, message = 0.0, None, None, ""
        action_type = action.get('action_type', '')

        if action_type == 'query_logs':
            svc = action.get('target_service')
            if svc not in self.scenario['logs']:
                message = f"Unknown service: {svc}"
            else:
                logs = self.scenario['logs'][svc]
                level = action.get('log_level')
                if level:
                    logs = [l for l in logs if f'[{level}]' in l]
                query_result = {'service': svc, 'logs': logs[:15]}
                self.queried_services.add(svc)
                if svc == self.scenario['affected_service']:
                    reward += 0.08
                    message = f"Retrieved logs for {svc}. Check for error patterns."
                else:
                    reward -= 0.01
                    message = f"Retrieved logs for {svc}. Service appears healthy."

        elif action_type == 'query_metrics':
            svc = action.get('target_service')
            if svc not in self.scenario['metrics']:
                message = f"Unknown service: {svc}"
            else:
                query_result = {'service': svc, 'metrics': self.scenario['metrics'][svc]}
                if svc == self.scenario['affected_service']:
                    reward += 0.06
                    message = f"Metrics retrieved for {svc}. Review anomalies carefully."
                else:
                    reward -= 0.01
                    message = f"Metrics for {svc} retrieved. Within normal range."

        elif action_type == 'query_alerts':
            query_result = {'alerts': self.scenario['alerts']}
            reward += 0.03
            message = "Active alerts retrieved."

        elif action_type == 'identify_cause':
            if self.root_cause_declared:
                reward -= 0.05; message = "Root cause already declared. Take action."
            else:
                self.root_cause_declared = True
                declared_svc   = action.get('suspected_service', '')
                declared_cause = action.get('suspected_cause', '')
                correct_svc    = self.scenario['affected_service']
                correct_cause  = self.scenario['root_cause']
                svc_ok   = declared_svc   == correct_svc
                cause_ok = declared_cause == correct_cause
                if svc_ok and cause_ok:
                    self.correct_cause = True; reward += 0.30
                    message = f"Correct! Root cause: {correct_cause} on {correct_svc}."
                elif svc_ok:
                    reward += 0.12; message = "Service correct but wrong cause type."
                elif cause_ok:
                    reward += 0.10; message = "Cause type correct but wrong service."
                else:
                    reward -= 0.10; message = "Incorrect. Re-investigate."

        elif action_type == 'take_action':
            mitigation = action.get('mitigation', '')
            allowed    = CORRECT_ACTIONS.get(self.scenario['root_cause'], [])
            if not self.root_cause_declared:
                reward -= 0.05; message = "Identify root cause before taking action."
            elif self.mitigation_taken:
                reward -= 0.05; message = "Mitigation already applied."
            else:
                self.mitigation_taken = True
                if mitigation in allowed:
                    self.correct_mitigation = True; reward += 0.40
                    message = f"Correct mitigation: {mitigation}. Service recovering..."
                elif mitigation == 'escalate_to_human':
                    reward += 0.05; message = "Escalated. Human engineer paged."
                    self.done = True
                else:
                    self.wrong_action_count += 1; reward -= 0.15
                    message = f"Wrong mitigation: {mitigation}. This may worsen the incident."

        elif action_type == 'verify_recovery':
            if not self.mitigation_taken:
                reward -= 0.03; message = "No mitigation applied yet to verify."
            elif self.correct_mitigation and not self.recovery_verified:
                self.recovery_verified = True; reward += 0.15
                message = "Service health confirmed. Incident resolved."
                self.done = True
            elif self.recovery_verified:
                reward -= 0.02; message = "Already verified."
            else:
                reward -= 0.05; message = "Service still degraded. Wrong mitigation was applied."
        else:
            message = f"Unknown action_type: {action_type}"

        # Efficiency penalty after optimal steps
        if self.step_count > OPTIMAL.get(self.task_name, 5):
            reward -= 0.02

        if self.step_count >= MAX_STEPS.get(self.task_name, 10):
            self.done = True; message += " | Max steps reached."

        self.cumulative_reward = min(1.0, max(0.0, self.cumulative_reward + reward))
        return self._make_obs(reward, self.done, message, query_result, action_result)

    def state(self) -> dict:
        score = 0.0
        if self.correct_cause:      score += 0.35
        if self.correct_mitigation: score += 0.40
        if self.recovery_verified:  score += 0.15
        if self.step_count <= OPTIMAL.get(self.task_name, 5): score += 0.10
        return {
            'episode_id': self.episode_id, 'task_name': self.task_name,
            'step_count': self.step_count, 'max_steps': MAX_STEPS.get(self.task_name,10),
            'done': self.done, 'root_cause_identified': self.root_cause_declared,
            'correct_cause_identified': self.correct_cause,
            'mitigation_taken': self.mitigation_taken,
            'correct_mitigation_taken': self.correct_mitigation,
            'recovery_verified': self.recovery_verified,
            'cumulative_reward': round(self.cumulative_reward, 3),
            'score': round(min(1.0, score), 3),
        }

    def _make_obs(self, reward, done, message, query_result=None, action_result=None) -> dict:
        return {
            'task_name':       self.scenario['task_name']        if self.scenario else '',
            'task_description':self.scenario['task_description'] if self.scenario else '',
            'system_overview': self.scenario['system_overview']  if self.scenario else {},
            'active_alerts':   self.scenario['alerts']           if self.scenario else [],
            'query_result': query_result, 'action_result': action_result,
            'reward': round(reward,3), 'done': done,
            'step_count': self.step_count, 'message': message,
        }
```

---

## Phase 5 — server/app.py

```python
import os
from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional
from environment import IncidentResponseEnvironment

app = FastAPI(title="Incident Response Triage Environment")

envs = {'easy': IncidentResponseEnvironment('easy'),
        'medium': IncidentResponseEnvironment('medium'),
        'hard': IncidentResponseEnvironment('hard')}

class ActionRequest(BaseModel):
    action_type: str
    target_service: Optional[str] = None
    metric_name: Optional[str] = None
    log_level: Optional[str] = None
    suspected_service: Optional[str] = None
    suspected_cause: Optional[str] = None
    mitigation: Optional[str] = None
    task_name: str = 'easy'

@app.post("/reset")
def reset(task_name: str = 'easy'):
    return envs.get(task_name, envs['easy']).reset()

@app.post("/step")
def step(request: ActionRequest):
    return envs.get(request.task_name, envs['easy']).step(request.dict())

@app.get("/state")
def state(task_name: str = 'easy'):
    return envs.get(task_name, envs['easy']).state()

@app.get("/health")
def health():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
```

---

## Phase 6 — Docker

**server/Dockerfile:**
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 7860
CMD ["python", "app.py"]
```

**server/requirements.txt:**
```
fastapi==0.111.0
uvicorn==0.29.0
pydantic==2.7.0
faker==24.0.0
numpy==1.26.4
python-dotenv==1.0.1
```

---

## Phase 7 — openenv.yaml

```yaml
name: incident-response-env
version: "1.0.0"
description: >
  RL environment simulating IT incident response. Agent investigates alerts,
  queries logs/metrics, identifies root causes, applies correct mitigations.
  3 difficulty levels: easy, medium, hard.
author: Team Gutka
tasks:
  - name: easy
    description: Single service failure with obvious root cause
    max_steps: 10
    reward_range: [0.0, 1.0]
  - name: medium
    description: Cascading microservice failure requiring dependency tracing
    max_steps: 18
    reward_range: [0.0, 1.0]
  - name: hard
    description: Intermittent race condition with misleading signals
    max_steps: 25
    reward_range: [0.0, 1.0]
tags: [openenv, incident-response, sre, devops, reinforcement-learning]
```

---

## Phase 8 — inference.py (ROOT LEVEL — mandatory)

```python
"""
Incident Response Triage — Baseline Inference Script
Required env vars: API_BASE_URL, MODEL_NAME, HF_TOKEN, ENV_URL
"""
import os, sys, json, requests
from openai import OpenAI

API_BASE_URL = os.getenv("API_BASE_URL", "https://router.huggingface.co/v1")
MODEL_NAME   = os.getenv("MODEL_NAME",   "Qwen/Qwen2.5-72B-Instruct")
HF_TOKEN     = os.getenv("HF_TOKEN",     "")
ENV_URL      = os.getenv("ENV_URL",      "http://localhost:8000")
TASKS        = ["easy", "medium", "hard"]
MAX_STEPS    = {"easy": 10, "medium": 18, "hard": 25}

client = OpenAI(api_key=HF_TOKEN, base_url=API_BASE_URL)

SYSTEM_PROMPT = """You are an expert SRE responding to a live incident.
Investigate by querying logs/metrics, identify root cause, apply correct fix.

action_types:
- query_logs:     {"action_type":"query_logs","target_service":"<svc>","log_level":"ERROR","task_name":"<task>"}
- query_metrics:  {"action_type":"query_metrics","target_service":"<svc>","task_name":"<task>"}
- query_alerts:   {"action_type":"query_alerts","task_name":"<task>"}
- identify_cause: {"action_type":"identify_cause","suspected_service":"<svc>","suspected_cause":"<cause>","task_name":"<task>"}
- take_action:    {"action_type":"take_action","mitigation":"<action>","task_name":"<task>"}
- verify_recovery:{"action_type":"verify_recovery","task_name":"<task>"}

Services: api-gateway, auth-service, payment-service, user-service, cache-service, db-primary, notification-svc
Root causes: OOM, BAD_DEPLOY, CONFIG_ERROR, DISK_FULL, DB_CONN_LIMIT, RACE_CONDITION
Mitigations: restart_service, rollback_deploy, fix_config, scale_out, cleanup_disk, increase_db_pool, flush_cache

Respond with ONLY valid JSON. No explanation. No markdown."""

def call_env(endpoint, payload=None, params=None):
    if endpoint == "reset":
        r = requests.post(f"{ENV_URL}/reset", params=params or {})
    elif endpoint == "step":
        r = requests.post(f"{ENV_URL}/step", json=payload)
    elif endpoint == "state":
        r = requests.get(f"{ENV_URL}/state", params=params or {})
    return r.json()

def get_action(messages):
    resp = client.chat.completions.create(
        model=MODEL_NAME, messages=messages, max_tokens=200, temperature=0.2)
    return resp.choices[0].message.content.strip()

def run_task(task_name):
    obs = call_env("reset", params={"task_name": task_name})
    print(f"[START] task={task_name} env=incident-response-env model={MODEL_NAME}")
    sys.stdout.flush()

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": (
            f"TASK: {task_name}\n"
            f"DESCRIPTION: {obs['task_description']}\n"
            f"SYSTEM STATUS: {json.dumps(obs['system_overview'], indent=2)}\n"
            f"ACTIVE ALERTS: {json.dumps(obs['active_alerts'], indent=2)}\n"
            "Begin investigation. Respond with your first action as JSON."
        )},
    ]

    rewards, step = [], 0

    for step in range(1, MAX_STEPS[task_name] + 1):
        try:
            raw_action = get_action(messages)
            action = json.loads(raw_action)
            action['task_name'] = task_name
        except Exception:
            action = {"action_type": "query_alerts", "task_name": task_name}
            raw_action = json.dumps(action)

        obs    = call_env("step", payload=action)
        reward = obs.get("reward", 0.0)
        done   = obs.get("done", False)
        rewards.append(reward)

        print(f"[STEP] step={step} action={action.get('action_type')} "
              f"reward={reward:.2f} done={str(done).lower()} error=null")
        sys.stdout.flush()

        messages.append({"role": "assistant", "content": raw_action})
        messages.append({"role": "user", "content": (
            f"Result: {obs.get('message','')}\n"
            f"Query result: {json.dumps(obs.get('query_result') or {})}\n"
            f"Step: {step}\nNext action (JSON only):"
        )})

        if done:
            break

    state  = call_env("state", params={"task_name": task_name})
    score  = state.get("score", 0.0)
    success = score >= 0.5
    rewards_str = ",".join(f"{r:.2f}" for r in rewards)
    print(f"[END] success={str(success).lower()} steps={step} "
          f"score={score:.2f} rewards={rewards_str}")
    sys.stdout.flush()
    return score

def main():
    for task in TASKS:
        run_task(task)

if __name__ == "__main__":
    main()
```

---

## Phase 9 — Local Testing

```bash
# Start server
cd server && pip install -r requirements.txt && python app.py

# Test endpoints
curl -X POST "http://localhost:8000/reset?task_name=easy"
curl -X POST "http://localhost:8000/step" -H "Content-Type: application/json" \
  -d '{"action_type":"query_logs","target_service":"api-gateway","task_name":"easy"}'
curl "http://localhost:8000/state?task_name=easy"

# Run inference locally
cd ..
export API_BASE_URL="https://router.huggingface.co/v1"
export MODEL_NAME="Qwen/Qwen2.5-72B-Instruct"
export HF_TOKEN="hf_your_token"
export ENV_URL="http://localhost:8000"
python inference.py

# Docker test
cd server
docker build -t incident-response-env .
docker run -p 8000:7860 incident-response-env
```

**Expected output format:**
```
[START] task=easy env=incident-response-env model=Qwen/Qwen2.5-72B-Instruct
[STEP] step=1 action=query_alerts reward=0.03 done=false error=null
[STEP] step=2 action=query_logs reward=0.08 done=false error=null
[END] success=true steps=5 score=0.85 rewards=0.03,0.08,...
```

---

## Phase 10 — HuggingFace Deployment

```bash
# Create HF Space: huggingface.co → New Space → Docker → Public
git init && git add . && git commit -m "Initial incident response env"
git remote add space https://huggingface.co/spaces/YOUR_USERNAME/incident-response-env
git push space main
```

**HF Space Secrets** (Settings → Variables and Secrets):
```
API_BASE_URL = https://router.huggingface.co/v1
MODEL_NAME   = Qwen/Qwen2.5-72B-Instruct
HF_TOKEN     = hf_your_token_here
```

**Verify:**
```bash
curl -X POST "https://YOUR_USERNAME-incident-response-env.hf.space/reset?task_name=easy"
# Must return HTTP 200 with JSON
```

---

## Phase 11 — Pre-Submission Validation

```bash
# Official validator
curl -fsSL https://raw.githubusercontent.com/meta-pytorch/OpenEnv/main/scripts/validate-submission.sh \
  | bash -s -- https://YOUR_USERNAME-incident-response-env.hf.space .

# OpenEnv validator
openenv validate .
```

**Manual checklist:**
- [ ] `inference.py` in ROOT directory (not in `server/`)
- [ ] `[START]` / `[STEP]` / `[END]` log format exact (field names, spacing)
- [ ] All 3 tasks return scores between 0.0 and 1.0
- [ ] Graders never return same score for all inputs
- [ ] `docker build` works from clean environment
- [ ] HF Space is **PUBLIC**
- [ ] README has: description, action/obs spaces, task descriptions, setup, baseline scores, example episode
- [ ] `openenv.yaml` has all required fields
- [ ] `API_BASE_URL`, `MODEL_NAME`, `HF_TOKEN` are env vars (not hardcoded)

---

## Phase 12 — README Must Include

1. What the environment simulates
2. Action space — all 6 action types with fields
3. Observation space — all fields
4. State fields — what `state()` returns
5. Task descriptions — easy / medium / hard
6. Reward breakdown
7. Setup instructions (local + Docker)
8. Baseline scores from `inference.py`
9. Example full episode (reset → end)

---

## Scoring Summary

| Component           | Points |
|---------------------|--------|
| Correct root cause  | +0.35  |
| Correct mitigation  | +0.40  |
| Recovery verified   | +0.15  |
| Efficiency bonus    | +0.10  |
| **Total**           | **1.00** |

Penalties: `-0.15` wrong mitigation, `-0.10` wrong cause, `-0.02/step` after optimal, `-0.02` extra queries

---

## Top 5 Disqualifiers

1. `inference.py` not in root directory
2. `[STEP]` log format even slightly wrong (extra space, wrong field name)
3. Docker build failing on HF infrastructure
4. Graders returning same score every time
5. HF Space is private instead of public
