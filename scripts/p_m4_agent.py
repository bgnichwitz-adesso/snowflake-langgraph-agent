"""M4 — verify agent code-artifact integration (cheap, mechanical).

Two tasks through the real agentic loop (no image rebuild — orchestrator/agent
unchanged; tasks seeded at runtime):

  task-multi     : solvable MULTI-FILE task (app.py imports a separate mathutil.py)
                   -> expect RUNS=DONE AND both files persisted on CODE_STAGE.
  task-feedback  : the required constant is NOT in the spec, only in the visible
                   test -> iter0 must FAIL, then converge to DONE via the visible
                   feedback (proves feedback-driven correction). If iter0 PASSES a
                   value not derivable from the spec, that flags a possible
                   held-out/stage read-leak.

MAX_ITER=3. Scope: code-only artifacts; depth/quality is deferred to the real
use-case run (not tested here).
"""
import sys

import config
from sf import connect

DB, SCHEMA, POOL = config.DATABASE, config.SCHEMA, config.POOL
CORE = f"{DB}.{SCHEMA}"
PROJECT = "DEMO"
ART = config.artifact_schema(PROJECT)
STAGE = f"{ART}.CODE_STAGE"
MAX_ITER = "3"
TASK_IDS = ("task-multi", "task-feedback")

TASKS = {
    "task-multi": {
        "spec": (
            "Build a small Python app IN THE CURRENT DIRECTORY. Create a SEPARATE "
            "module `mathutil.py` defining `add(a, b)` and `mul(a, b)`, and an "
            "`app.py` defining `run()` that imports mathutil and returns "
            "add(2, 3) + mul(2, 3). entry_point = app.py.\n\n"
            "Visible tests (test_visible.py):\n"
            "from app import run\n"
            "def test_run():\n    r = run()\n    assert type(r) is int and r == 11\n"
        ),
        "visible": "from app import run\n"
                   "def test_run():\n    r = run()\n    assert type(r) is int and r == 11\n",
        "heldout": "from app import run\n"
                   "def test_run_typed():\n    r = run()\n    assert isinstance(r, int) and r == 11\n",
        "expect": "DONE",
    },
    "task-feedback": {
        # The required value is intentionally NOT in the spec AND is unguessable
        # (a 7-digit non-cultural number — NOT 42, which a model guesses blind).
        # The agent can only learn it from the failing visible test fed back after
        # iter0. So a genuine iter0 PASS would prove a read-leak, not a lucky guess.
        "spec": (
            "Write solution.py defining a function `secret()` that returns the "
            "required integer value. The exact value is enforced by the tests; "
            "make the tests pass.\n"
        ),
        "visible": "from solution import secret\n"
                   "def test_secret():\n    r = secret()\n    assert type(r) is int and r == 6829473\n",
        "heldout": "from solution import secret\n"
                   "def test_secret2():\n    assert secret() == 6829473\n",
        "expect": "DONE",
    },
}


def seed(cur) -> None:
    """Seed TASK_SPECS + frozen tests into the separate TEST_VISIBLE / TEST_HELDOUT
    tables (NOT the mounted stage) so the developer agent cannot read them."""
    for task, t in TASKS.items():
        cur.execute(
            f"INSERT INTO {CORE}.TASK_SPECS "
            "(task_id, project_id, user_id, status, title, spec_text) "
            "VALUES (%s,%s,%s,%s,%s,%s)",
            (task, PROJECT, "tester", "LOCKED", task, t["spec"]),
        )
        cur.execute(
            f"INSERT INTO {ART}.TEST_VISIBLE (task_id, filename, content) "
            "VALUES (%s,%s,%s)", (task, "test_visible.py", t["visible"]))
        cur.execute(
            f"INSERT INTO {ART}.TEST_HELDOUT (task_id, filename, content) "
            "VALUES (%s,%s,%s)", (task, "test_heldout.py", t["heldout"]))
        print(f"  seeded {task} (spec + TEST_VISIBLE + TEST_HELDOUT)")


def run_loop(cur, tag: str, task: str) -> None:
    job = f"{CORE}.M4_{task.replace('-', '_').upper()}"
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
        CORTEX_MODEL: "{config.CORTEX_MODEL}"
        AGENT_MAX_TURNS: "{config.AGENT_MAX_TURNS}"
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


def _runs_status(cur, task):
    cur.execute(f"SELECT status FROM {ART}.RUNS WHERE task_id = %s "
                "ORDER BY created_at DESC LIMIT 1", (task,))
    row = cur.fetchone()
    return row[0] if row else None


def main() -> int:
    tag = sys.argv[1] if len(sys.argv) > 1 else "latest"
    try:
        with connect() as conn:
            cur = conn.cursor()
            print("=== seed tasks + frozen tests (into tables) ===")
            seed(cur)
            for task in TASK_IDS:
                run_loop(cur, tag, task)

            # --- Test A: task-multi -> DONE + multi-file persisted on stage ---
            multi_status = _runs_status(cur, "task-multi")
            cur.execute(f"LIST @{STAGE}/task-multi")
            names = [r[0] for r in cur.fetchall()]
            iter_files = [n for n in names if "/iter-" in n]
            has_app = any(n.endswith("app.py") for n in iter_files)
            has_helper = any(n.endswith("mathutil.py") for n in iter_files)
            a_ok = multi_status == "DONE" and has_app and has_helper

            # --- Test B: task-feedback -> iter0 FAIL then DONE (feedback-driven) ---
            fb_status = _runs_status(cur, "task-feedback")
            cur.execute(f"SELECT iteration, passed FROM {ART}.TEST_RESULTS "
                        "WHERE task_id = 'task-feedback' ORDER BY iteration")
            traj = cur.fetchall()
            iter0_passed = any(it == 0 and bool(p) for it, p in traj)
            iter0_failed = any(it == 0 and not bool(p) for it, p in traj)
            later_passed = any(it > 0 and bool(p) for it, p in traj)
            b_ok = fb_status == "DONE" and iter0_failed and later_passed
            leak = iter0_passed  # passed an unknowable-from-spec value at iter0

            print("\n=== M4 RESULTS ===")
            print(f"  A task-multi:  status={multi_status} app.py={has_app} "
                  f"mathutil.py={has_helper} -> {'OK' if a_ok else 'FAIL'}")
            print(f"  B task-feedback: status={fb_status} traj={traj} "
                  f"iter0_failed={iter0_failed} later_passed={later_passed} "
                  f"-> {'OK' if b_ok else 'FAIL'}")
            if leak:
                print("  ⚠ WARN: task-feedback passed at iter0 — the agent solved a "
                      "value not in the spec → possible held-out/stage read-leak.")

            # cleanup
            for task in TASK_IDS:
                cur.execute(f"REMOVE @{STAGE}/{task}")
            ids = "', '".join(TASK_IDS)
            cur.execute(f"DELETE FROM {CORE}.TASK_SPECS WHERE project_id = '{PROJECT}' "
                        f"AND task_id IN ('{ids}')")
            for tbl in ("DEV_COMMENTS", "TEST_RESULTS", "RUNS",
                        "TEST_VISIBLE", "TEST_HELDOUT"):
                cur.execute(f"DELETE FROM {ART}.{tbl} WHERE task_id IN ('{ids}')")
            cur.execute(f"ALTER COMPUTE POOL {POOL} SUSPEND")

        ok = a_ok and b_ok and not leak
        print(f"\n{'PASS — multi-file flows + feedback-driven convergence + persistence' if ok else 'FAIL'}")
        return 0 if ok else 1
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
