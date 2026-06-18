"""Deterministic gate — the single decision point of the orchestrator.

Reads the latest TEST_RESULTS row for a (task, iteration) and decides PASS/FAIL
based ONLY on the recorded exit code (0 = pass). No LLM judgement, no parsing of
output. Connection-agnostic: pass any cursor (works from the container or the
laptop).
"""


def gate(cur, artifact_schema: str, task_id: str, iteration: int) -> dict:
    cur.execute(
        f"SELECT exit_code, passed, created_at FROM {artifact_schema}.TEST_RESULTS "
        "WHERE task_id = %s AND iteration = %s "
        "ORDER BY created_at DESC LIMIT 1",
        (task_id, int(iteration)),
    )
    row = cur.fetchone()
    if row is None:
        return {"decision": "FAIL", "reason": "no test result", "exit_code": None}
    exit_code = row[0]
    decision = "PASS" if exit_code == 0 else "FAIL"
    return {"decision": decision, "reason": f"exit_code={exit_code}",
            "exit_code": exit_code}
