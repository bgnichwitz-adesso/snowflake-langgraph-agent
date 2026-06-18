"""Paket 1.5 — deterministic test runner (runs inside the SPCS container).

For each task dir under the mounted CODE_STAGE, runs pytest, captures the exit
code + output, and appends a row to <ARTIFACT_SCHEMA>.TEST_RESULTS. The exit
code is the single source of truth — the gate (app/gate.py) reads ONLY that.

Env:
  ARTIFACT_SCHEMA  e.g. ORCHESTRATOR.DEMO   (where TEST_RESULTS lives)
  MOUNT_PATH       default /workspace        (CODE_STAGE mount)
  TASKS            space-separated "<task_id>/<iteration>" pairs to run
"""
import os
import subprocess
import sys

import snowflake.connector

MOUNT = os.environ.get("MOUNT_PATH", "/workspace")
ARTIFACT_SCHEMA = os.environ["ARTIFACT_SCHEMA"]
TASKS = os.environ.get("TASKS", "").split()


def _connect():
    with open("/snowflake/session/token") as fh:
        token = fh.read()
    return snowflake.connector.connect(
        host=os.environ["SNOWFLAKE_HOST"],
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        token=token,
        authenticator="oauth",
        warehouse=os.environ.get("SNOWFLAKE_WAREHOUSE", "DEFAULT_WH"),
    )


def run_pytest(workdir: str):
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q"],
        cwd=workdir, capture_output=True, text=True,
    )
    return proc.returncode, (proc.stdout + proc.stderr)


def main() -> int:
    if not TASKS:
        print("TEST_RUNNER_FAIL: no TASKS given", flush=True)
        return 1

    conn = _connect()
    cur = conn.cursor()
    all_ok = True
    print("TEST_RUNNER_BEGIN", flush=True)
    for pair in TASKS:
        task_id, _, iteration = pair.partition("/")
        iteration = iteration or "0"
        workdir = os.path.join(MOUNT, task_id, iteration)
        if not os.path.isdir(workdir):
            print(f"  {pair}: MISSING dir {workdir}", flush=True)
            all_ok = False
            continue
        rc, output = run_pytest(workdir)
        passed = rc == 0
        cur.execute(
            f"INSERT INTO {ARTIFACT_SCHEMA}.TEST_RESULTS "
            "(task_id, iteration, tool, exit_code, passed, output) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (task_id, int(iteration), "pytest", rc, passed, output[:5000]),
        )
        print(f"  {pair}: exit_code={rc} passed={passed}", flush=True)
        all_ok = all_ok and passed
    print("TEST_RUNNER_END", flush=True)
    conn.close()
    # The runner itself returns 0 if it ran cleanly; pass/fail of the tasks is
    # recorded in TEST_RESULTS for the gate to decide on.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
