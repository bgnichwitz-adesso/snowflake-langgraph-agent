"""Package 3 — run the in-container Cortex test as a job service and surface
its logs as evidence.

EXECUTE JOB SERVICE blocks until the container exits; we then pull container
logs via SYSTEM$GET_SERVICE_LOGS and check for the response markers.
"""
import sys

from sf import connect

DB = "PREPSMART"
SCHEMA = "ORCHESTRATOR"
POOL = "PREPSMART_POOL_XS"
JOB = "CORTEX_TEST_JOB"
FQ_JOB = f"{DB}.{SCHEMA}.{JOB}"

SPEC = """
spec:
  containers:
    - name: main
      image: /prepsmart/orchestrator/images/orchestrator_base:p3
      command: ["python", "-u", "/app/cortex_test.py"]
"""

EXECUTE_JOB = f"""
EXECUTE JOB SERVICE
  IN COMPUTE POOL {POOL}
  NAME = {FQ_JOB}
  FROM SPECIFICATION $${SPEC}$$
"""


def main() -> int:
    try:
        with connect() as conn:
            cur = conn.cursor()
            cur.execute(f"DROP SERVICE IF EXISTS {FQ_JOB}")
            print("=== EXECUTE JOB SERVICE (blocks until done) ===")
            try:
                cur.execute(EXECUTE_JOB)
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
