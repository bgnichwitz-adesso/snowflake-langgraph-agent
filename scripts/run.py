"""Form A launcher — start the in-container LangGraph orchestrator for a task.

Thin on purpose: it only EXECUTE JOB SERVICEs the orchestrator (as ORCH_PROJ via the
RUNNER->PROJ chain) and waits. The deterministic LangGraph loop runs INSIDE that
container and launches the ORCH_TEST / ORCH_DEV child jobs itself (nested). There is NO
host-side loop. Usage: run.py --task <task_id> [--tag latest] [--max-iter 3]
"""
import argparse
import sys

import config
from sf import connect


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", required=True)
    ap.add_argument("--tag", default="latest")
    ap.add_argument("--max-iter", default="3")
    a = ap.parse_args()
    task = a.task
    try:
        with connect() as conn:
            cur = conn.cursor()
            cur.execute("SELECT CURRENT_USER()")
            user = cur.fetchone()[0]
            cur.execute(f"GRANT ROLE {config.RUNNER_ROLE} TO USER {user}")
            cur.execute(f"SELECT project_id FROM {config.DATABASE}.{config.SCHEMA}."
                        "TASK_SPECS_CURRENT WHERE task_id = %s AND status = 'LOCKED'", (task,))
            row = cur.fetchone()
            if not row:
                raise RuntimeError(f"no LOCKED task {task}")
            pid = row[0]
            art = config.artifact_schema(pid)
            proj = config.project_role(pid)
            job = f"{art}.ORCH_{task.replace('-', '_').upper()}"
            env = {
                "TASK_ID": task,
                "CORE_SCHEMA": f"{config.DATABASE}.{config.SCHEMA}",
                "MAX_ITER": str(a.max_iter),
                "ORCH_IMAGE": config.spec_image_path(a.tag),
                "ORCH_POOL": config.POOL,
                "XSTAGE": config.exchange_stage(pid),
                "XSCHEMA": config.exchange_schema(pid),
                "DEV_ROLE": config.dev_role(pid),
                "TESTER_ROLE": config.tester_role(pid),
                "SNOWFLAKE_WAREHOUSE": config.WAREHOUSE,
                "CORTEX_MODEL": config.CORTEX_MODEL,
                "AGENT_MAX_TURNS": config.AGENT_MAX_TURNS,
            }
            env_lines = "".join(f'\n        {k}: "{v}"' for k, v in env.items())
            spec = f"""
spec:
  containers:
    - name: main
      image: {config.spec_image_path(a.tag)}
      command: ["python", "-u", "/app/orchestrator.py"]
      env:{env_lines}
      volumeMounts:
        - name: xchg
          mountPath: /xchg
  volumes:
    - name: xchg
      source: "@{config.exchange_stage(pid)}"
"""
            cur.execute(f"DROP SERVICE IF EXISTS {job}")
            cur.execute(f"USE ROLE {config.RUNNER_ROLE}")
            cur.execute(f"USE ROLE {proj}")
            print(f"=== EXECUTE ORCHESTRATOR {task} as {proj} (LangGraph loop in-container) ===")
            try:
                cur.execute(f"EXECUTE JOB SERVICE IN COMPUTE POOL {config.POOL} "
                            f"NAME = {job} FROM SPECIFICATION $${spec}$$")
            except Exception as exc:  # noqa: BLE001
                print(f"  orchestrator raised: {type(exc).__name__}: {str(exc)[:200]}")
            cur.execute("USE ROLE ACCOUNTADMIN")
            cur.execute(f"SELECT SYSTEM$GET_SERVICE_LOGS('{job}', '0', 'main', 1000)")
            print((cur.fetchone()[0] or "")[-2800:])
            cur.execute(f"DROP SERVICE IF EXISTS {job}")
            cur.execute(f"SELECT status FROM {art}.RUNS WHERE task_id = %s "
                        "ORDER BY created_at DESC LIMIT 1", (task,))
            r = cur.fetchone()
            status = r[0] if r else None
            cur.execute(f"ALTER COMPUTE POOL {config.POOL} SUSPEND")
        print(f"\nFINAL: {status}")
        return 0 if status in ("DONE", "NEEDS_HUMAN") else 1
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
