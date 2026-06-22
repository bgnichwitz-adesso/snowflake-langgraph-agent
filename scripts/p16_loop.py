"""Paket 1.6 — prove the orchestrator loop end to end.

Seeds two LOCKED tasks for project DEMO and stages their frozen tests
(visible + held-out), then runs the in-container LangGraph loop per task:
  - task-add        : solvable -> expect RUNS.status = DONE
  - task-impossible : held-out test contradicts the visible one -> expect
                      RUNS.status = NEEDS_HUMAN after MAX_ITER

Uses MAX_ITER=3 to keep the unsolvable run quick (default in code is 10).
"""
import os
import sys
import tempfile

import config
from sf import connect

DB, SCHEMA, POOL = config.DATABASE, config.SCHEMA, config.POOL
CORE = f"{DB}.{SCHEMA}"
PROJECT = "DEMO"
ART = config.artifact_schema(PROJECT)
STAGE = f"{ART}.CODE_STAGE"
MAX_ITER = "3"

# --- task fixtures: spec_text (prompt) + visible/held-out test files ---
TASKS = {
    "task-add": {
        "spec": (
            "Write solution.py defining a function add(a, b) that returns the "
            "sum of a and b.\n\nVisible tests (test_visible.py):\n"
            "from solution import add\n"
            "def test_add():\n    assert add(2, 2) == 4\n"
        ),
        "visible": "from solution import add\n"
                   "def test_add():\n    assert add(2, 2) == 4\n",
        "heldout": "from solution import add\n"
                   "def test_add_more():\n    assert add(3, 5) == 8\n"
                   "    assert add(-1, 1) == 0\n",
        "expect": "DONE",
    },
    "task-impossible": {
        "spec": (
            "Write solution.py defining a function val() that returns the "
            "required value.\n\nVisible tests (test_visible.py):\n"
            "from solution import val\n"
            "def test_val():\n    assert val() == 4\n"
        ),
        "visible": "from solution import val\n"
                   "def test_val():\n    assert val() == 4\n",
        # held-out contradicts the visible test -> unsatisfiable on purpose
        "heldout": "from solution import val\n"
                   "def test_val_secret():\n    assert val() == 5\n",
        "expect": "NEEDS_HUMAN",
    },
}


def seed_and_stage(cur, tmp: str) -> None:
    for task, t in TASKS.items():
        cur.execute(
            f"INSERT INTO {CORE}.TASK_SPECS "
            "(task_id, project_id, user_id, status, title, spec_text) "
            "VALUES (%s,%s,%s,%s,%s,%s)",
            (task, PROJECT, "tester", "LOCKED", task, t["spec"]),
        )
        d = os.path.join(tmp, task)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "test_visible.py"), "w") as fh:
            fh.write(t["visible"])
        with open(os.path.join(d, "test_heldout.py"), "w") as fh:
            fh.write(t["heldout"])
        cur.execute(
            f"PUT 'file://{d}/*.py' @{STAGE}/{task}/tests/ "
            "AUTO_COMPRESS=FALSE OVERWRITE=TRUE"
        )
        print(f"  seeded + staged {task}")


def run_loop(cur, tag: str, task: str) -> None:
    job = f"{CORE}.LOOP_{task.replace('-', '_').upper()}"
    spec = f"""
spec:
  containers:
    - name: main
      image: {config.spec_image_path(tag)}
      command: ["python", "-u", "/app/orchestrator.py"]
      env:
        TASK_ID: {task}
        CORE_SCHEMA: {CORE}
        MAX_ITER: "{MAX_ITER}"
        MOUNT_PATH: /workspace
        SNOWFLAKE_WAREHOUSE: "{config.WAREHOUSE}"
      volumeMounts:
        - name: code
          mountPath: /workspace
  volumes:
    - name: code
      source: "@{STAGE}"
"""
    cur.execute(f"DROP SERVICE IF EXISTS {job}")
    print(f"\n=== LOOP for {task} ===")
    try:
        cur.execute(f"EXECUTE JOB SERVICE IN COMPUTE POOL {POOL} NAME = {job} "
                    f"FROM SPECIFICATION $${spec}$$")
    except Exception as exc:  # noqa: BLE001
        print(f"  job raised: {type(exc).__name__}: {str(exc)[:160]}")
    cur.execute(f"SELECT SYSTEM$GET_SERVICE_LOGS('{job}', '0', 'main', 1000)")
    print(cur.fetchone()[0] or "")
    cur.execute(f"DROP SERVICE IF EXISTS {job}")


def latest_status(cur, task: str):
    cur.execute(
        f"SELECT status, detail FROM {ART}.RUNS WHERE task_id = %s "
        "ORDER BY created_at DESC LIMIT 1", (task,))
    return cur.fetchone()


def main() -> int:
    tag = sys.argv[1] if len(sys.argv) > 1 else "latest"
    try:
        with connect() as conn:
            cur = conn.cursor()
            print("=== seed tasks + stage frozen tests ===")
            with tempfile.TemporaryDirectory() as tmp:
                seed_and_stage(cur, tmp)

            for task in TASKS:
                run_loop(cur, tag, task)

            print("\n=== RUNS outcomes ===")
            results = {}
            for task, t in TASKS.items():
                row = latest_status(cur, task)
                status = row[0] if row else None
                results[task] = status
                print(f"  {task}: status={status} (expected {t['expect']})  "
                      f"detail={row[1][:80] if row else None!r}")

            # cleanup: stage, seeded specs, artifact rows, pool
            for task in TASKS:
                cur.execute(f"REMOVE @{STAGE}/{task}")
            cur.execute(f"DELETE FROM {CORE}.TASK_SPECS WHERE project_id = '{PROJECT}' "
                        "AND task_id IN ('task-add','task-impossible')")
            for tbl in ("DEV_COMMENTS", "TEST_RESULTS", "RUNS"):
                cur.execute(f"DELETE FROM {ART}.{tbl} "
                            "WHERE task_id IN ('task-add','task-impossible')")
            cur.execute(f"ALTER COMPUTE POOL {POOL} SUSPEND")

        ok = all(results.get(t) == TASKS[t]["expect"] for t in TASKS)
        print(f"\n{'PASS — loop: solvable→DONE, unsolvable→NEEDS_HUMAN' if ok else 'FAIL'}")
        return 0 if ok else 1
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
