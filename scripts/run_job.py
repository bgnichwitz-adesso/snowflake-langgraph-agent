"""Generic SPCS job-service runner: run a command in the orchestrator image,
block until done, print container logs, and assert an expected substring.

Usage:
  run_job.py --tag p4 --name LANGGRAPH_CHECK_JOB --expect langgraph -- \\
      python -u -c "import langgraph; print('langgraph', langgraph.__version__)"
"""
import argparse
import sys

import config
from sf import connect

DB = config.DATABASE
SCHEMA = config.SCHEMA
POOL = config.POOL


def build_spec(tag: str, command: list[str]) -> str:
    cmd_yaml = ", ".join(f'"{c}"' for c in command)
    return f"""
spec:
  containers:
    - name: main
      image: {config.spec_image_path(tag)}
      command: [{cmd_yaml}]
      env:
        CORTEX_MODEL: "{config.CORTEX_MODEL}"
        SNOWFLAKE_WAREHOUSE: "{config.WAREHOUSE}"
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--expect", required=True)
    ap.add_argument("command", nargs=argparse.REMAINDER)
    a = ap.parse_args()
    command = a.command[1:] if a.command and a.command[0] == "--" else a.command
    if not command:
        print("FAIL: no command given", file=sys.stderr)
        return 1

    fq_job = f"{DB}.{SCHEMA}.{a.name}"
    spec = build_spec(a.tag, command)
    execute_job = f"""
EXECUTE JOB SERVICE
  IN COMPUTE POOL {POOL}
  NAME = {fq_job}
  FROM SPECIFICATION $${spec}$$
"""
    try:
        with connect() as conn:
            cur = conn.cursor()
            cur.execute(f"DROP SERVICE IF EXISTS {fq_job}")
            print(f"=== EXECUTE JOB SERVICE {fq_job} ===")
            try:
                cur.execute(execute_job)
                print("  job finished")
            except Exception as exc:  # noqa: BLE001
                print(f"  job raised: {type(exc).__name__}: {exc}")

            print("\n=== CONTAINER LOGS ===")
            cur.execute(
                f"SELECT SYSTEM$GET_SERVICE_LOGS('{fq_job}', '0', 'main', 1000)"
            )
            logs = cur.fetchone()[0]
            print(logs)

        if a.expect in (logs or ""):
            print(f"\nPASS — found expected '{a.expect}'")
            return 0
        print(f"\nFAIL: expected '{a.expect}' not in logs", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
