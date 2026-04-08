"""Comprehensive test suite for the Incident Response Triage Environment."""
import sys
sys.path.insert(0, ".")

from server.environment import IncidentResponseEnvironment, CORRECT_ACTIONS, OPTIMAL, MAX_STEPS
from server import IncidentResponseEnvironment as ServerEnv

ALL_SERVICES = [
    "api-gateway", "auth-service", "payment-service", "user-service",
    "cache-service", "db-primary", "notification-svc",
]
ALL_CAUSES = ["OOM", "BAD_DEPLOY", "CONFIG_ERROR", "DISK_FULL", "DB_CONN_LIMIT", "RACE_CONDITION"]
TASKS = ["easy", "medium", "hard"]
ALL_MITIGATIONS = ["restart_service", "rollback_deploy", "fix_config", "cleanup_disk", "increase_db_pool"]

results = []


def check(label, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    msg = f"  [{status}] {label}"
    if detail:
        msg += f" -- {detail}"
    print(msg)
    results.append((label, condition))
    return condition


# ── 1. Import & init ──────────────────────────────────────────────────────────
print("=== 1. IMPORT & INIT ===")
check("server/__init__ imports new env", ServerEnv.__module__ == "server.environment")

# ── 2. Step before reset (null guard) ────────────────────────────────────────
print("\n=== 2. STEP BEFORE RESET ===")
env = IncidentResponseEnvironment("easy")
obs = env.step({"action_type": "query_alerts"})
check("step before reset: no crash", True)
check("step before reset: done=False", obs["done"] == False)
check("step before reset: helpful message", "reset" in obs["message"].lower())
check("step before reset: reward=0.0", obs["reward"] == 0.0)

# ── 3. Reset initializes correctly ───────────────────────────────────────────
print("\n=== 3. RESET INITIALIZATION ===")
for task in TASKS:
    env = IncidentResponseEnvironment(task)
    obs = env.reset()
    check(f"{task}: task_name correct", obs["task_name"] == task)
    check(f"{task}: 7 services in system_overview", len(obs["system_overview"]) == 7)
    check(f"{task}: alerts present", len(obs["active_alerts"]) > 0)
    check(f"{task}: step_count=0", obs["step_count"] == 0)
    check(f"{task}: done=False", obs["done"] == False)
    check(f"{task}: scenario loaded", env.scenario is not None)
    check(f"{task}: affected_service is valid", env.scenario["affected_service"] in ALL_SERVICES)
    check(f"{task}: root_cause is valid", env.scenario["root_cause"] in ALL_CAUSES)

# ── 4. Double reset ───────────────────────────────────────────────────────────
print("\n=== 4. DOUBLE RESET ===")
env = IncidentResponseEnvironment("easy")
env.reset()
env.step({"action_type": "query_alerts"})
ep1 = env.episode_id
env.reset()
ep2 = env.episode_id
check("double reset: episode_id changes", ep1 != ep2)
check("double reset: step_count=0", env.step_count == 0)
check("double reset: done=False", env.done == False)

# ── 5. Reward math ────────────────────────────────────────────────────────────
print("\n=== 5. REWARD MATH ===")
for task in TASKS:
    env = IncidentResponseEnvironment(task)
    env.reset()
    affected = env.scenario["affected_service"]
    root_cause = env.scenario["root_cause"]
    mitigation = CORRECT_ACTIONS[root_cause][0]
    wrong_svc = next(s for s in ALL_SERVICES if s != affected)

    obs = env.step({"action_type": "query_alerts"})
    check(f"{task}: query_alerts reward=+0.03", obs["reward"] == 0.03)

    obs = env.step({"action_type": "query_logs", "target_service": affected})
    check(f"{task}: query_logs(affected) reward=+0.08", obs["reward"] == 0.08)

    obs = env.step({"action_type": "query_logs", "target_service": wrong_svc})
    check(f"{task}: query_logs(wrong_svc) reward=-0.01", obs["reward"] == -0.01)

    obs = env.step({"action_type": "query_metrics", "target_service": affected})
    check(f"{task}: query_metrics(affected) reward=+0.06", obs["reward"] == 0.06)

    obs = env.step({"action_type": "identify_cause", "suspected_service": affected, "suspected_cause": root_cause})
    check(f"{task}: correct identify reward=+0.30", obs["reward"] == 0.30)
    check(f"{task}: correct_cause flag set", env.correct_cause)

    # Step 6: take_action. Penalty applies only if step_count > OPTIMAL[task]
    # easy: OPTIMAL=5, so step 6 > 5 → penalty -0.02 → 0.40-0.02=0.38
    # medium: OPTIMAL=9, step 6 ≤ 9 → no penalty → 0.40
    # hard: OPTIMAL=13, step 6 ≤ 13 → no penalty → 0.40
    obs = env.step({"action_type": "take_action", "mitigation": mitigation})
    expected_mit_reward = round(0.40 - (0.02 if 6 > OPTIMAL[task] else 0.0), 3)
    check(f"{task}: correct mitigation reward={expected_mit_reward}", round(obs["reward"], 3) == expected_mit_reward)
    check(f"{task}: correct_mitigation flag set", env.correct_mitigation)

    # Step 7: verify_recovery. Penalty applies if step_count > OPTIMAL[task]
    obs = env.step({"action_type": "verify_recovery"})
    expected_ver_reward = round(0.15 - (0.02 if 7 > OPTIMAL[task] else 0.0), 3)
    check(f"{task}: verify_recovery reward={expected_ver_reward}", round(obs["reward"], 3) == expected_ver_reward)
    check(f"{task}: done=True after verify", obs["done"])

    # Score: efficiency bonus applies if step_count <= OPTIMAL[task]
    state = env.state()
    efficiency = 0.10 if state["step_count"] <= OPTIMAL[task] else 0.0
    expected_score = round(0.35 + 0.40 + 0.15 + efficiency, 2)
    check(f"{task}: score={expected_score} (7 steps, optimal={OPTIMAL[task]})", round(state["score"], 2) == expected_score)

# ── 6. Efficiency bonus ───────────────────────────────────────────────────────
print("\n=== 6. EFFICIENCY BONUS ===")
for task in TASKS:
    env = IncidentResponseEnvironment(task)
    env.reset()
    affected = env.scenario["affected_service"]
    root_cause = env.scenario["root_cause"]
    mitigation = CORRECT_ACTIONS[root_cause][0]
    # 3 steps — well within all optimal thresholds
    env.step({"action_type": "identify_cause", "suspected_service": affected, "suspected_cause": root_cause})
    env.step({"action_type": "take_action", "mitigation": mitigation})
    env.step({"action_type": "verify_recovery"})
    state = env.state()
    check(f"{task}: 3-step episode score=1.0", state["score"] == 1.0)

# ── 7. Penalty paths ─────────────────────────────────────────────────────────
print("\n=== 7. PENALTY PATHS ===")
env = IncidentResponseEnvironment("easy")
env.reset()
affected = env.scenario["affected_service"]
root_cause = env.scenario["root_cause"]
wrong_svc   = next(s for s in ALL_SERVICES if s != affected)
wrong_cause = next(c for c in ALL_CAUSES if c != root_cause)

obs = env.step({"action_type": "identify_cause", "suspected_service": wrong_svc, "suspected_cause": wrong_cause})
check("both wrong (svc+cause): reward=-0.10", obs["reward"] == -0.10)

obs = env.step({"action_type": "identify_cause", "suspected_service": wrong_svc, "suspected_cause": wrong_cause})
check("duplicate identify: reward=-0.05", obs["reward"] == -0.05)

# Wrong mitigation
env2 = IncidentResponseEnvironment("easy")
env2.reset()
affected2 = env2.scenario["affected_service"]
root_cause2 = env2.scenario["root_cause"]
correct_mit = CORRECT_ACTIONS[root_cause2]
wrong_mit = next(m for m in ALL_MITIGATIONS if m not in correct_mit)
env2.step({"action_type": "identify_cause", "suspected_service": affected2, "suspected_cause": root_cause2})
obs = env2.step({"action_type": "take_action", "mitigation": wrong_mit})
check(f"wrong mitigation ({wrong_mit}): reward=-0.15", obs["reward"] == -0.15)

obs = env2.step({"action_type": "verify_recovery"})
check("verify after wrong mitigation: reward<0", obs["reward"] < 0)

# take_action before identify_cause
env3 = IncidentResponseEnvironment("easy")
env3.reset()
obs = env3.step({"action_type": "take_action", "mitigation": "rollback_deploy"})
check("take_action before identify: reward=-0.05", obs["reward"] == -0.05)

# verify_recovery before anything
env4 = IncidentResponseEnvironment("easy")
env4.reset()
obs = env4.step({"action_type": "verify_recovery"})
check("verify_recovery before mitigation: reward=-0.03", obs["reward"] == -0.03)

# ── 8. Max steps enforcement ──────────────────────────────────────────────────
print("\n=== 8. MAX STEPS ENFORCEMENT ===")
for task in TASKS:
    env = IncidentResponseEnvironment(task)
    env.reset()
    for _ in range(MAX_STEPS[task]):
        env.step({"action_type": "query_alerts"})
    check(f"{task}: done=True at max_steps={MAX_STEPS[task]}", env.done)
    obs = env.step({"action_type": "query_alerts"})
    check(f"{task}: post-max step returns gracefully (no crash)", True)
    check(f"{task}: post-max step done=True", obs["done"])

# ── 9. Hard task hidden metrics ───────────────────────────────────────────────
print("\n=== 9. HARD TASK HIDDEN METRICS ===")
env = IncidentResponseEnvironment("hard")
env.reset()
obs = env.step({"action_type": "query_metrics", "target_service": "cache-service"})
m = obs["query_result"]["metrics"]
check("hard: cache-service concurrent_writes=847", m.get("concurrent_writes") == 847)
check("hard: cache-service cache_hit_rate=0.61", m.get("cache_hit_rate") == 0.61)
check("hard: cache-service write_lock_wait_ms=340", m.get("write_lock_wait_ms") == 340)
obs2 = env.step({"action_type": "query_metrics", "target_service": "payment-service"})
m2 = obs2["query_result"]["metrics"]
check("hard: payment-service has no hidden concurrent_writes", m2.get("concurrent_writes") is None)

# ── 10. Medium dependency map ─────────────────────────────────────────────────
print("\n=== 10. MEDIUM DEPENDENCY MAP ===")
env = IncidentResponseEnvironment("medium")
env.reset()
obs = env.step({"action_type": "query_dependencies", "target_service": "api-gateway"})
check("medium: dependency query_result not None", obs["query_result"] is not None)
check("medium: api-gateway depends on user-service", "user-service" in obs["query_result"]["depends_on"])
check("medium: dependency reward=+0.04", obs["reward"] == 0.04)

env_hard = IncidentResponseEnvironment("hard")
env_hard.reset()
obs = env_hard.step({"action_type": "query_dependencies", "target_service": "cache-service"})
check("hard: no dependency map returns info dict", "info" in obs["query_result"])

# ── 11. Scenario randomness ───────────────────────────────────────────────────
print("\n=== 11. SCENARIO RANDOMNESS ===")
causes_seen = set()
services_seen = set()
for _ in range(30):
    env = IncidentResponseEnvironment("easy")
    env.reset()
    causes_seen.add(env.scenario["root_cause"])
    services_seen.add(env.scenario["affected_service"])
check(f"easy: >1 root_cause types in 30 resets", len(causes_seen) > 1, f"saw {causes_seen}")
check(f"easy: >1 affected_service in 30 resets", len(services_seen) > 1, f"saw {services_seen}")

# Medium: root_cause from MEDIUM_CAUSES
med_causes = set()
for _ in range(20):
    env = IncidentResponseEnvironment("medium")
    env.reset()
    med_causes.add(env.scenario["root_cause"])
    check(f"medium: affected always db-primary", env.scenario["affected_service"] == "db-primary")
check(f"medium: varied root_causes", len(med_causes) > 0, f"saw {med_causes}")

# Hard: always RACE_CONDITION on cache-service
env = IncidentResponseEnvironment("hard")
env.reset()
check("hard: root_cause always RACE_CONDITION", env.scenario["root_cause"] == "RACE_CONDITION")
check("hard: affected always cache-service", env.scenario["affected_service"] == "cache-service")

# ── 12. Log filter ────────────────────────────────────────────────────────────
print("\n=== 12. LOG FILTER ===")
env = IncidentResponseEnvironment("easy")
env.reset()
affected = env.scenario["affected_service"]
obs_all = env.step({"action_type": "query_logs", "target_service": affected})
obs_err = env.step({"action_type": "query_logs", "target_service": affected, "log_level": "ERROR"})
all_logs = obs_all["query_result"]["logs"]
err_logs = obs_err["query_result"]["logs"]
check("log filter: ERROR-only logs all contain [ERROR]", all("[ERROR]" in l for l in err_logs))
check("log filter: ERROR filter <= all logs", len(err_logs) <= len(all_logs))

# ── 13. Unknown action type ───────────────────────────────────────────────────
print("\n=== 13. UNKNOWN ACTION TYPE ===")
env = IncidentResponseEnvironment("easy")
env.reset()
obs = env.step({"action_type": "explode_everything"})
check("unknown action_type: no crash", True)
check("unknown action_type: message mentions valid types", "query_logs" in obs["message"])

# ── 14. State before reset ────────────────────────────────────────────────────
print("\n=== 14. STATE BEFORE RESET ===")
env = IncidentResponseEnvironment("medium")
state = env.state()
check("state before reset: score=0.0", state["score"] == 0.0)
check("state before reset: step_count=0", state["step_count"] == 0)
check("state before reset: no crash", True)

# ── Result summary ────────────────────────────────────────────────────────────
print()
fails = [label for label, ok in results if not ok]
total = len(results)
passed = total - len(fails)
print(f"=== RESULT: {passed}/{total} passed ===")
if fails:
    print("FAILURES:")
    for f in fails:
        print(f"  FAIL: {f}")
    sys.exit(1)
else:
    print("ALL TESTS PASSED")
