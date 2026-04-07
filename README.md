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

An OpenEnv RL environment where an AI agent acts as an SRE responding to live production incidents. The agent must investigate system alerts, query logs and metrics, identify root causes, and apply the correct mitigation.

## Tasks

| Task | Description | Max Steps |
|------|-------------|-----------|
| `easy` | Single service failure with obvious root cause | 10 |
| `medium` | Cascading microservice failure requiring dependency tracing | 18 |
| `hard` | Intermittent race condition with misleading signals | 25 |

## API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Liveness probe |
| `/schema` | GET | Action/observation schemas |
| `/reset?task_name=easy` | POST | Start new episode |
| `/step` | POST | Execute one action |
| `/state?task_name=easy` | GET | Current episode state and score |

## Action Types

```json
{"action_type": "query_logs", "target_service": "<svc>", "log_level": "ERROR", "task_name": "<task>"}
{"action_type": "query_metrics", "target_service": "<svc>", "task_name": "<task>"}
{"action_type": "query_alerts", "task_name": "<task>"}
{"action_type": "query_dependencies", "target_service": "<svc>", "task_name": "<task>"}
{"action_type": "identify_cause", "suspected_cause": "<cause>", "task_name": "<task>"}
{"action_type": "take_action", "mitigation": "<mitigation>", "task_name": "<task>"}
{"action_type": "verify_recovery", "task_name": "<task>"}
```

## Scoring

- Correct root cause identified: +0.35
- Correct mitigation applied: +0.40
- Recovery verified: +0.15
- Efficiency bonus (within optimal steps): +0.10
- Per-step penalty after optimal: -0.02/step

## Quick Start

```python
import requests

BASE = "https://Himanshuraj03000-incident-response-env.hf.space"

# Reset
obs = requests.post(f"{BASE}/reset", params={"task_name": "easy"}).json()

# Step
result = requests.post(f"{BASE}/step", json={
    "action_type": "query_alerts",
    "task_name": "easy"
}).json()
```
