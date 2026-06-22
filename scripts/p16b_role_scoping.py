"""Paket 1.6b — prove the loop runs under the project execution role.

Launch chain: user → USE ROLE ORCH_RUNNER → USE ROLE ORCH_PROJ_<ID> →
EXECUTE JOB SERVICE (owned by the project role, named in its artifact schema).
The container session then runs AS the project role (no ACCOUNTADMIN). We verify
the loop log reports CURRENT_ROLE = ORCH_PROJ_DEMO and the run reaches DONE.

Prereq: register_project has applied the service-execution grants (re-run it).
"""
import os
import sys
import tempfile

import config
from sf import connect

DB, SCHEMA, POOL = config.DATABASE, config.SCHEMA, config.POOL
CORE = f"{DB}.{SCHEMA}"
PROJECT = "DEMO"
ROLE = config.project_role(PROJECT)          # ORCH_PROJ_DEMO
ART = config.artifact_schema(PROJECT)
STAGE = f"{ART}.CODE_STAGE"
JOB = f"{ART}.LOOP_ROLE_TEST"                 # named in the project's own schema
TASK = "task-role"

SPEC_TEXT = (
    "Write solution.py defining a function add(a, b) that returns the sum.\n\n"
    "Visible tests (test_visible.py):\n"
    "from solution import add\ndef test_add():\n    assert add(2, 2) == 4\n"
)
VISIBLE = "from solution import add\ndef test_add():\n    assert add(2, 2) == 4\n"
HELDOUT = "from solution import add\ndef test_more():\n    assert add(10, 5) == 15\n"


def main() -> int:
    tag = sys.argv[1] if len(sys.argv) > 1 else "latest"
    spec = f"""
spec:
  containers:
    - name: main
      image: {config.spec_image_path(tag)}
      command: ["python", "-u", "/app/orchestrator.py"]
      env:
        TASK_ID: {TASK}
        CORE_SCHEMA: {CORE}
        MAX_ITER: "3"
        MOUNT_PATH: /workspace
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
            cur.execute("SELECT CURRENT_USER()")
            user = cur.fetchone()[0]

            # one-time: let the user assume RUNNER (admin action, idempotent)
            cur.execute(f"GRANT ROLE {config.RUNNER_ROLE} TO USER {user}")
            print(f"granted {config.RUNNER_ROLE} to user {user}")

            # seed task + stage frozen tests (as admin)
            cur.execute(
                f"INSERT INTO {CORE}.TASK_SPECS "
                "(task_id, project_id, user_id, status, title, spec_text) "
                "VALUES (%s,%s,%s,%s,%s,%s)",
                (TASK, PROJECT, "tester", "LOCKED", TASK, SPEC_TEXT))
            with tempfile.TemporaryDirectory() as tmp:
                with open(os.path.join(tmp, "test_visible.py"), "w") as fh:
                    fh.write(VISIBLE)
                with open(os.path.join(tmp, "test_heldout.py"), "w") as fh:
                    fh.write(HELDOUT)
                cur.execute(f"PUT 'file://{tmp}/*.py' @{STAGE}/{TASK}/tests/ "
                            "AUTO_COMPRESS=FALSE OVERWRITE=TRUE")
            print("seeded + staged task-role")

            # launch chain: RUNNER -> PROJ -> EXECUTE (owner = PROJ)
            cur.execute(f"DROP SERVICE IF EXISTS {JOB}")
            cur.execute(f"USE ROLE {config.RUNNER_ROLE}")
            cur.execute(f"USE ROLE {ROLE}")
            print(f"\n=== EXECUTE JOB SERVICE as {ROLE} ===")
            try:
                cur.execute(f"EXECUTE JOB SERVICE IN COMPUTE POOL {POOL} NAME = {JOB} "
                            f"FROM SPECIFICATION $${spec}$$")
                print("  job finished")
            except Exception as exc:  # noqa: BLE001
                print(f"  job raised: {type(exc).__name__}: {str(exc)[:200]}")

            # back to admin for log read + cleanup
            cur.execute("USE ROLE ACCOUNTADMIN")
            cur.execute(f"SELECT SYSTEM$GET_SERVICE_LOGS('{JOB}', '0', 'main', 1000)")
            logs = cur.fetchone()[0] or ""
            print("\n=== CONTAINER LOGS ===")
            print(logs)

            cur.execute(f"SELECT status FROM {ART}.RUNS WHERE task_id = %s "
                        "ORDER BY created_at DESC LIMIT 1", (TASK,))
            row = cur.fetchone()
            status = row[0] if row else None

            # cleanup
            cur.execute(f"REMOVE @{STAGE}/{TASK}")
            cur.execute(f"DELETE FROM {CORE}.TASK_SPECS WHERE task_id = '{TASK}'")
            for t in ("DEV_COMMENTS", "TEST_RESULTS", "RUNS"):
                cur.execute(f"DELETE FROM {ART}.{t} WHERE task_id = '{TASK}'")
            cur.execute(f"DROP SERVICE IF EXISTS {JOB}")
            cur.execute(f"ALTER COMPUTE POOL {POOL} SUSPEND")

        ran_as_proj = f"running as role: {ROLE}" in logs
        print(f"\nran as {ROLE}: {ran_as_proj}")
        print(f"RUNS status: {status}")
        ok = ran_as_proj and status == "DONE"
        print(f"\n{'PASS — loop ran least-privilege as ' + ROLE + ' → DONE' if ok else 'FAIL'}")
        return 0 if ok else 1
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
