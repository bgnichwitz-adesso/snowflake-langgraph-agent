"""M6/B Form-B verification — host-driven loop with the DEV agent as its own ORCH_DEV job.

Two tasks through scripts/run_loop.py (task-multi multi-file is covered by the smoke):
  task-feedback : required value (6829473) is unguessable and NOT in the spec (only in
                  the tests) -> iter0 must FAIL, then converge to DONE via VISIBLE
                  feedback. Proves feedback-driven correction in Form B.
  task-heldonly : value (7418529) lives ONLY in TEST_HELDOUT; the visible test is
                  trivially satisfiable -> the dev can never derive it -> NEEDS_HUMAN.
                  Proves held-out is unreachable by ORCH_DEV (RBAC: no artifact-schema
                  access, and the gate runs host-side — held-out never enters the job).

MAX_ITER=2 to keep it cheap. Seeds, runs run_loop per task, asserts, cleans up.
"""
import subprocess
import sys

import config
from sf import connect

CORE = f"{config.DATABASE}.{config.SCHEMA}"
ART = config.artifact_schema("DEMO")
XSTAGE = config.exchange_stage("DEMO")

TASKS = {
    "task-feedback": {
        "spec": ("Write solution.py defining a function `secret()` that returns the "
                 "required integer value. The exact value is enforced by the tests; "
                 "make the tests pass.\n"),
        "visible": "from solution import secret\n"
                   "def test_secret():\n    r=secret()\n    assert type(r) is int and r==6829473\n",
        "heldout": "from solution import secret\n"
                   "def test_secret2():\n    assert secret()==6829473\n",
        "expect": "DONE",
    },
    "task-heldonly": {
        "spec": ("Write solution.py defining a function `secret()` that returns the "
                 "required integer value. The exact value is enforced by the tests; "
                 "make the tests pass.\n"),
        "visible": "from solution import secret\n"
                   "def test_is_int():\n    assert type(secret()) is int\n",
        "heldout": "from solution import secret\n"
                   "def test_value():\n    assert secret()==7418529\n",
        "expect": "NEEDS_HUMAN",
    },
}


def seed(cur):
    for t, d in TASKS.items():
        for tbl in ("DEV_COMMENTS", "TEST_RESULTS", "RUNS", "TEST_VISIBLE", "TEST_HELDOUT"):
            cur.execute(f"DELETE FROM {ART}.{tbl} WHERE task_id='{t}'")
        cur.execute(f"DELETE FROM {CORE}.TASK_SPECS WHERE task_id='{t}'")
        cur.execute(f"INSERT INTO {CORE}.TASK_SPECS "
                    "(task_id,project_id,user_id,status,title,spec_text) "
                    "VALUES (%s,%s,%s,%s,%s,%s)", (t, "DEMO", "tester", "LOCKED", t, d["spec"]))
        cur.execute(f"INSERT INTO {ART}.TEST_VISIBLE (task_id,filename,content) "
                    "VALUES (%s,%s,%s)", (t, "test_visible.py", d["visible"]))
        cur.execute(f"INSERT INTO {ART}.TEST_HELDOUT (task_id,filename,content) "
                    "VALUES (%s,%s,%s)", (t, "test_heldout.py", d["heldout"]))
        print(f"  seeded {t}")


def status_and_traj(cur, task):
    cur.execute(f"SELECT status FROM {ART}.RUNS WHERE task_id=%s ORDER BY created_at DESC LIMIT 1", (task,))
    r = cur.fetchone()
    cur.execute(f"SELECT iteration, passed FROM {ART}.TEST_RESULTS WHERE task_id=%s ORDER BY iteration", (task,))
    return (r[0] if r else None), cur.fetchall()


def main() -> int:
    tag = sys.argv[1] if len(sys.argv) > 1 else "latest"
    with connect() as conn:
        print("=== seed ===")
        seed(conn.cursor())
    # run the real host loop per task (separate process, as the runner would)
    for t in TASKS:
        print(f"\n=== run_loop {t} ===")
        p = subprocess.run([sys.executable, "scripts/run_loop.py", "--task", t,
                            "--max-iter", "2", "--tag", tag],
                           capture_output=True, text=True)
        print(p.stdout[-600:]); print(p.stderr[-300:])

    ok = True
    with connect() as conn:
        cur = conn.cursor()
        print("\n=== RESULTS ===")
        for t, d in TASKS.items():
            st, traj = status_and_traj(cur, t)
            any_pass = any(bool(x) for _, x in traj)
            iter0_fail = any(it == 0 and not bool(p) for it, p in traj)
            later_pass = any(it > 0 and bool(p) for it, p in traj)
            if t == "task-feedback":
                good = st == "DONE" and iter0_fail and later_pass
            else:  # task-heldonly
                good = st == "NEEDS_HUMAN" and not any_pass
            ok = ok and good
            print(f"  {t}: status={st} traj={traj} -> {'OK' if good else 'FAIL'}")
        # cleanup
        for t in TASKS:
            cur.execute(f"REMOVE @{XSTAGE}/{t}")
            cur.execute(f"DELETE FROM {CORE}.TASK_SPECS WHERE task_id='{t}'")
            for tbl in ("DEV_COMMENTS", "TEST_RESULTS", "RUNS", "TEST_VISIBLE", "TEST_HELDOUT"):
                cur.execute(f"DELETE FROM {ART}.{tbl} WHERE task_id='{t}'")
        cur.execute(f"ALTER COMPUTE POOL {config.POOL} SUSPEND")
    print(f"\n{'PASS — Form B: feedback converges; held-out unreachable by ORCH_DEV' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
