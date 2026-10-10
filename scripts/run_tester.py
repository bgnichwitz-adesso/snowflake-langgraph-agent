"""1.8 — host step: generate the frozen tests for a task via the TESTER agent.

Launches a TESTER SPCS job OWNED BY ORCH_TEST_<ID> (chain RUNNER->ORCH_TEST) that
authors test_visible.py + test_heldout.py from the spec and writes them to the
exchange stage. The host then INSERTS them into TEST_VISIBLE / TEST_HELDOUT as admin
(host-mediated: the tester never writes the authoritative tables directly). Run this
BEFORE the developer loop (scripts/run_loop.py). Usage:
  run_tester.py --task <task_id> [--tag latest]
"""
import argparse
import json
import os
import sys
import tempfile

import config
from sf import connect

ADMIN = "ACCOUNTADMIN"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", required=True)
    ap.add_argument("--tag", default="latest")
    a = ap.parse_args()
    task = a.task

    try:
        with connect() as conn:
            cur = conn.cursor()
            cur.execute("SELECT CURRENT_USER()")
            user = cur.fetchone()[0]
            cur.execute(f"GRANT ROLE {config.RUNNER_ROLE} TO USER {user}")  # idempotent

            cur.execute(f"SELECT project_id, spec_text FROM "
                        f"{config.DATABASE}.{config.SCHEMA}.TASK_SPECS_CURRENT "
                        "WHERE task_id = %s AND status = 'LOCKED'", (task,))
            row = cur.fetchone()
            if not row:
                raise RuntimeError(f"no LOCKED task {task}")
            project_id, spec_text = row
            art = config.artifact_schema(project_id)
            tester = config.tester_role(project_id)
            xstage = config.exchange_stage(project_id)
            xschema = config.exchange_schema(project_id)
            print(f"task {task} (project {project_id}); tester={tester}", flush=True)

            workdir = tempfile.mkdtemp(prefix=f"tester_{task}_")
            local_in = os.path.join(workdir, "_input.json")
            with open(local_in, "w") as fh:
                json.dump({"spec": spec_text}, fh)
            sdir = f"@{xstage}/{task}/tester"
            cur.execute(f"REMOVE {sdir}")
            cur.execute(f"PUT 'file://{local_in}' {sdir}/ AUTO_COMPRESS=FALSE OVERWRITE=TRUE")

            job = f"{xschema}.TESTERJOB_{task.replace('-', '_').upper()}"
            spec = f"""
spec:
  containers:
    - name: main
      image: {config.spec_image_path(a.tag)}
      command: ["python", "-u", "/app/tester_job.py"]
      env:
        TASK_ID: {task}
        XCHG_MOUNT: /xchg
        SNOWFLAKE_WAREHOUSE: "{config.WAREHOUSE}"
        CORTEX_MODEL: "{config.CORTEX_MODEL}"
        AGENT_MAX_TURNS: "{config.AGENT_MAX_TURNS}"
      volumeMounts:
        - name: xchg
          mountPath: /xchg
  volumes:
    - name: xchg
      source: "@{xstage}"
"""
            cur.execute(f"DROP SERVICE IF EXISTS {job}")
            cur.execute(f"USE ROLE {config.RUNNER_ROLE}")
            cur.execute(f"USE ROLE {tester}")
            print(f"=== EXECUTE TESTER JOB as {tester} ===", flush=True)
            try:
                cur.execute(f"EXECUTE JOB SERVICE IN COMPUTE POOL {config.POOL} "
                            f"NAME = {job} FROM SPECIFICATION $${spec}$$")
            except Exception as exc:  # noqa: BLE001
                print(f"  job raised: {type(exc).__name__}: {str(exc)[:160]}", flush=True)
            cur.execute(f"USE ROLE {ADMIN}")
            cur.execute(f"SELECT SYSTEM$GET_SERVICE_LOGS('{job}', '0', 'main', 500)")
            print((cur.fetchone()[0] or "")[-600:], flush=True)

            # collect the two test files + insert (host-mediated) into the frozen tables
            outd = os.path.join(workdir, "out")
            os.makedirs(outd, exist_ok=True)
            cur.execute(f"GET {sdir}/out/ 'file://{outd}/'")
            cur.execute(f"DROP SERVICE IF EXISTS {job}")

            inserted = {}
            for fn, table in (("test_visible.py", "TEST_VISIBLE"),
                              ("test_heldout.py", "TEST_HELDOUT")):
                p = os.path.join(outd, fn)
                if not os.path.exists(p):
                    print(f"  MISSING {fn} — tester did not produce it", flush=True)
                    continue
                content = open(p).read()
                cur.execute(f"DELETE FROM {art}.{table} WHERE task_id = %s", (task,))
                cur.execute(f"INSERT INTO {art}.{table} (task_id, filename, content) "
                            "VALUES (%s,%s,%s)", (task, fn, content))
                inserted[table] = len(content)
            cur.execute(f"ALTER COMPUTE POOL {config.POOL} SUSPEND")

        ok = "TEST_VISIBLE" in inserted and "TEST_HELDOUT" in inserted
        print(f"\ninserted: {inserted}")
        print(f"{'PASS — tester authored visible + held-out tests for ' + task if ok else 'FAIL — missing test file(s)'}")
        return 0 if ok else 1
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
