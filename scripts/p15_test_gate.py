"""Paket 1.5 — prove the test runner + deterministic gate end to end.

Stages two fixtures on CODE_STAGE (a passing and a failing solution), runs the
in-container test runner over both (stage mounted), then applies the gate from
the laptop. Expected: task-pass -> PASS row, task-fail -> FAIL row, and the gate
agrees based only on the exit code.
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

import config
from gate import gate
from sf import connect

DB, SCHEMA, POOL = config.DATABASE, config.SCHEMA, config.POOL
PROJECT = "DEMO"
ART = config.artifact_schema(PROJECT)        # ORCHESTRATOR.DEMO
STAGE = f"{ART}.CODE_STAGE"
JOB = f"{DB}.{SCHEMA}.TEST_GATE_JOB"

TEST_FILE = (
    "from solution import solution\n"
    "def test_solution():\n"
    "    assert solution() == 4\n"
)
FIXTURES = {                       # task_id -> solution.py body
    "task-pass": "def solution():\n    return 4\n",
    "task-fail": "def solution():\n    return 5\n",
}


def stage_fixtures(cur, tmp: str) -> None:
    for task, sol in FIXTURES.items():
        d = os.path.join(tmp, task)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "solution.py"), "w") as fh:
            fh.write(sol)
        with open(os.path.join(d, "test_solution.py"), "w") as fh:
            fh.write(TEST_FILE)
        cur.execute(
            f"PUT 'file://{d}/*.py' @{STAGE}/{task}/0/ "
            "AUTO_COMPRESS=FALSE OVERWRITE=TRUE"
        )


def main() -> int:
    tag = sys.argv[1] if len(sys.argv) > 1 else "latest"
    spec = f"""
spec:
  containers:
    - name: main
      image: {config.spec_image_path(tag)}
      command: ["python", "-u", "/app/test_runner.py"]
      env:
        ARTIFACT_SCHEMA: {ART}
        MOUNT_PATH: /workspace
        TASKS: "task-pass/0 task-fail/0"
        SNOWFLAKE_WAREHOUSE: "{config.WAREHOUSE}"
      volumeMounts:
        - name: code
          mountPath: /workspace
  volumes:
    - name: code
      source: "@{STAGE}"
"""
    try:
        with connect() as conn:
            cur = conn.cursor()
            with tempfile.TemporaryDirectory() as tmp:
                print("=== stage fixtures (PUT) ===")
                stage_fixtures(cur, tmp)
                print("  staged task-pass, task-fail")

            cur.execute(f"DROP SERVICE IF EXISTS {JOB}")
            print("\n=== EXECUTE JOB SERVICE (test runner) ===")
            try:
                cur.execute(
                    f"EXECUTE JOB SERVICE IN COMPUTE POOL {POOL} NAME = {JOB} "
                    f"FROM SPECIFICATION $${spec}$$"
                )
                print("  job finished")
            except Exception as exc:  # noqa: BLE001
                print(f"  job raised: {type(exc).__name__}: {str(exc)[:160]}")

            print("\n=== CONTAINER LOGS ===")
            cur.execute(f"SELECT SYSTEM$GET_SERVICE_LOGS('{JOB}', '0', 'main', 1000)")
            print(cur.fetchone()[0] or "")

            print("=== GATE (reads only exit_code) ===")
            g_pass = gate(cur, ART, "task-pass", 0)
            g_fail = gate(cur, ART, "task-fail", 0)
            print(f"  task-pass -> {g_pass}")
            print(f"  task-fail -> {g_fail}")

            # cleanup: stage fixtures + results rows + service + pool
            cur.execute(f"REMOVE @{STAGE}/task-pass")
            cur.execute(f"REMOVE @{STAGE}/task-fail")
            cur.execute(f"DELETE FROM {ART}.TEST_RESULTS "
                        "WHERE task_id IN ('task-pass', 'task-fail')")
            cur.execute(f"DROP SERVICE IF EXISTS {JOB}")
            cur.execute(f"ALTER COMPUTE POOL {POOL} SUSPEND")

        ok = g_pass["decision"] == "PASS" and g_fail["decision"] == "FAIL"
        print(f"\n{'PASS — gate: green→PASS, red→FAIL (exit-code only)' if ok else 'FAIL'}")
        return 0 if ok else 1
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
