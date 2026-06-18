"""Paket 1.4 — run the stage-I/O test as a job-service with CODE_STAGE mounted,
then verify from the laptop that the file actually persisted to the stage.

Mounts the project's CODE_STAGE as a filesystem volume, the container writes a
file under <task>/<iter>/, and we confirm via LIST @stage that it landed.
"""
import sys

import config
from sf import connect

DB, SCHEMA, POOL = config.DATABASE, config.SCHEMA, config.POOL
PROJECT = "DEMO"
ART = config.artifact_schema(PROJECT)        # ORCHESTRATOR.DEMO
STAGE = f"{ART}.CODE_STAGE"
JOB = f"{DB}.{SCHEMA}.STAGE_IO_JOB"
TASK_ID = "task-demo"
ITER = "0"


def main() -> int:
    tag = sys.argv[1] if len(sys.argv) > 1 else "latest"
    spec = f"""
spec:
  containers:
    - name: main
      image: {config.spec_image_path(tag)}
      command: ["python", "-u", "/app/stage_io.py"]
      env:
        MOUNT_PATH: /workspace
        TASK_ID: {TASK_ID}
        ITERATION: "{ITER}"
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
            cur.execute(f"DROP SERVICE IF EXISTS {JOB}")
            print("=== EXECUTE JOB SERVICE (stage mounted) ===")
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
            logs = cur.fetchone()[0] or ""
            print(logs)

            print(f"\n=== LIST @{STAGE} (persistence check) ===")
            cur.execute(f"LIST @{STAGE}")
            cols = [c[0].lower() for c in cur.description]
            files = [dict(zip(cols, r)) for r in cur.fetchall()]
            for f in files:
                print(f"  {f.get('name')}  ({f.get('size')} bytes)")

            # cleanup compute
            cur.execute(f"DROP SERVICE IF EXISTS {JOB}")
            cur.execute(f"ALTER COMPUTE POOL {POOL} SUSPEND")

        expected = f"{TASK_ID}/{ITER}/solution.py"
        log_ok = "roundtrip_ok: True" in logs
        persisted = any(expected in (f.get("name") or "") for f in files)
        print(f"\nlog roundtrip ok : {log_ok}")
        print(f"persisted on stage: {persisted} (expected …/{expected})")
        if log_ok and persisted:
            print("\nPASS — container wrote to mounted stage AND it persisted")
            return 0
        print("\nFAIL — stage I/O did not fully verify", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
