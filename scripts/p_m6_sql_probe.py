"""M6/B positive proof — the agent runs SQL under its least-priv PAT identity.

Least-priv launch (container/gate = ORCH_PROJ via SPCS token), ENFORCE sandbox
(only file tools + the "SQL" tool; Bash denied), agent SQL identity = ORCH_APP_<ID>
via the mounted PAT secret. Task can only be solved by querying Snowflake:

  SAFE + WORKS: agent uses the SQL tool as ORCH_APP to count rows in the project
  fixture table -> DONE. Proves SQL is enabled AND runs under the least-priv role.

Prereq: register_project (creates ORCH_APP_<ID> + grants) and setup_agent_identity
(service user + PAT secret) have run. MAX_ITER=2.
"""
import sys

import config
from sf import connect

DB, SCHEMA, POOL = config.DATABASE, config.SCHEMA, config.POOL
CORE = f"{DB}.{SCHEMA}"
PROJECT = "DEMO"
ART = config.artifact_schema(PROJECT)
STAGE = f"{ART}.CODE_STAGE"
ROLE = config.project_role(PROJECT)          # ORCH_PROJ_DEMO (owner/gate)
ROLE_APP = config.app_role(PROJECT)          # ORCH_APP_DEMO (agent SQL identity)
RUNNER = config.RUNNER_ROLE
MAX_ITER = "2"
TASK = "task-sqlprobe"

# DEMO_PROJ.PUBLIC.SAMPLE_DATA is empty (0 rows); knowable only by querying.
SPEC = (
    "Write solution.py defining a function row_count() that returns the number of "
    "rows in the Snowflake table DEMO_PROJ.PUBLIC.SAMPLE_DATA. You MUST query "
    "Snowflake to determine it (do not hardcode a guess). entry_point = solution.py.\n"
)
VISIBLE = ("from solution import row_count\n"
           "def test_rc():\n    r = row_count()\n    assert type(r) is int and r == 0\n")
HELDOUT = ("from solution import row_count\n"
           "def test_rc2():\n    assert row_count() == 0\n")


def main() -> int:
    tag = sys.argv[1] if len(sys.argv) > 1 else "latest"
    job = f"{ART}.SQLPROBE"
    spec = f"""
spec:
  containers:
    - name: main
      image: {config.spec_image_path(tag)}
      command: ["python", "-u", "/app/orchestrator.py"]
      env:
        TASK_ID: {TASK}
        CORE_SCHEMA: {CORE}
        MAX_ITER: "{MAX_ITER}"
        MOUNT_PATH: /workspace
        SNOWFLAKE_WAREHOUSE: "{config.WAREHOUSE}"
        CORTEX_MODEL: "{config.CORTEX_MODEL}"
        AGENT_MAX_TURNS: "{config.AGENT_MAX_TURNS}"
        AGENT_SANDBOX: "on"
        AGENT_USER: "{config.AGENT_USER}"
        AGENT_ROLE: "{ROLE_APP}"
      volumeMounts:
        - name: code
          mountPath: /workspace
      secrets:
        - snowflakeSecret: {config.app_pat_secret(PROJECT)}
          secretKeyRef: secret_string
          envVarName: AGENT_PAT
  volumes:
    - name: code
      source: "@{STAGE}"
"""
    try:
        with connect() as conn:
            cur = conn.cursor()
            print("=== seed task-sqlprobe (needs SQL); least-priv + PAT ===")
            cur.execute(
                f"INSERT INTO {CORE}.TASK_SPECS "
                "(task_id, project_id, user_id, status, title, spec_text) "
                "VALUES (%s,%s,%s,%s,%s,%s)",
                (TASK, PROJECT, "tester", "LOCKED", TASK, SPEC))
            cur.execute(f"INSERT INTO {ART}.TEST_VISIBLE (task_id, filename, content) "
                        "VALUES (%s,%s,%s)", (TASK, "test_visible.py", VISIBLE))
            cur.execute(f"INSERT INTO {ART}.TEST_HELDOUT (task_id, filename, content) "
                        "VALUES (%s,%s,%s)", (TASK, "test_heldout.py", HELDOUT))

            cur.execute(f"DROP SERVICE IF EXISTS {job}")
            cur.execute("SELECT CURRENT_USER()")
            user = cur.fetchone()[0]
            cur.execute(f"GRANT ROLE {RUNNER} TO USER {user}")   # idempotent
            cur.execute(f"USE ROLE {RUNNER}")
            cur.execute(f"USE ROLE {ROLE}")                       # owner = PROJ
            print("=== LOOP (least-priv, enforce, SQL enabled) ===")
            try:
                cur.execute(f"EXECUTE JOB SERVICE IN COMPUTE POOL {POOL} NAME = {job} "
                            f"FROM SPECIFICATION $${spec}$$")
            except Exception as exc:  # noqa: BLE001
                print(f"  job raised: {type(exc).__name__}: {str(exc)[:200]}")
            cur.execute("USE ROLE ACCOUNTADMIN")
            cur.execute(f"SELECT SYSTEM$GET_SERVICE_LOGS('{job}', '0', 'main', 1000)")
            logs = cur.fetchone()[0] or ""
            print(logs)
            cur.execute(f"DROP SERVICE IF EXISTS {job}")

            cur.execute(f"SELECT status FROM {ART}.RUNS WHERE task_id = %s "
                        "ORDER BY created_at DESC LIMIT 1", (TASK,))
            row = cur.fetchone()
            status = row[0] if row else None
            sql_allowed = any("allow tool=SQL" in ln for ln in logs.splitlines())

            print("\n=== SQL POSITIVE PROOF RESULTS ===")
            print(f"  RUNS status : {status}")
            print(f"  SQL tool used (allow tool=SQL): {sql_allowed}")

            # cleanup
            cur.execute(f"REMOVE @{STAGE}/{TASK}")
            cur.execute(f"DELETE FROM {CORE}.TASK_SPECS WHERE task_id = '{TASK}'")
            for tbl in ("DEV_COMMENTS", "TEST_RESULTS", "RUNS",
                        "TEST_VISIBLE", "TEST_HELDOUT"):
                cur.execute(f"DELETE FROM {ART}.{tbl} WHERE task_id = '{TASK}'")
            cur.execute(f"ALTER COMPUTE POOL {POOL} SUSPEND")

        ok = status == "DONE" and sql_allowed
        print(f"\n{'PASS — agent ran SQL as least-priv ORCH_APP and solved it' if ok else 'FAIL'}")
        return 0 if ok else 1
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
