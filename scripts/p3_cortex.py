"""Package 3 — run the in-container Cortex test as a job service and surface
its logs as evidence.

EXECUTE JOB SERVICE blocks until the container exits; we then pull container
logs via SYSTEM$GET_SERVICE_LOGS and check for the response markers.
"""
import sys

import config
from sf import connect

DB = config.DATABASE
SCHEMA = config.SCHEMA
POOL = config.POOL
JOB = "CORTEX_TEST_JOB"
FQ_JOB = f"{DB}.{SCHEMA}.{JOB}"


def main() -> int:
    tag = sys.argv[1] if len(sys.argv) > 1 else "p3"
    spec = f"""
spec:
  containers:
    - name: main
      image: {config.spec_image_path(tag)}
      command: ["python", "-u", "/app/cortex_test.py"]
      env:
        CORTEX_MODEL: "{config.CORTEX_MODEL}"
        SNOWFLAKE_WAREHOUSE: "{config.WAREHOUSE}"
"""
    execute_job = f"""
EXECUTE JOB SERVICE
  IN COMPUTE POOL {POOL}
  NAME = {FQ_JOB}
  FROM SPECIFICATION $${spec}$$
"""
    try:
        with connect() as conn:
            cur = conn.cursor()
            cur.execute(f"DROP SERVICE IF EXISTS {FQ_JOB}")
            print("=== EXECUTE JOB SERVICE (blocks until done) ===")
            try:
                cur.execute(execute_job)
                print(f"  job finished: {FQ_JOB}")
            except Exception as exc:  # noqa: BLE001 - still try to read logs
                print(f"  job raised: {type(exc).__name__}: {exc}")

            print("\n=== CONTAINER LOGS ===")
            cur.execute(
                f"SELECT SYSTEM$GET_SERVICE_LOGS('{FQ_JOB}', '0', 'main', 1000)"
            )
            logs = cur.fetchone()[0]
            print(logs)

        if "CORTEX_RESPONSE_BEGIN" in logs and "CORTEX_FAIL" not in logs:
            print("\nPASS — Cortex responded from inside the container")
            return 0
        print("\nFAIL: no valid Cortex response in logs", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
