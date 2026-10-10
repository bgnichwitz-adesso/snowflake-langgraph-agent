"""Deterministic LangGraph orchestrator loop (runs IN-CONTAINER as ORCH_PROJ).

Form A — the loop stays in the container and in LangGraph; its nodes launch CHILD
SPCS jobs (nested EXECUTE JOB SERVICE) for the work that needs a different identity:

    START → ensure_tests → generate → run_tests → gate ─┬─ PASS → finalize(done) → END
                             ↑                           ├─ FAIL (iter<MAX) → next_iter ┘
                             └───────────────────────────┘
                                                         └─ iter≥MAX → finalize(NEEDS_HUMAN)

- ensure_tests: if no frozen tests exist, launch the TESTER job (as ORCH_TEST) which
  authors test_visible.py + test_heldout.py; the orchestrator (ORCH_PROJ) inserts them
  into TEST_VISIBLE / TEST_HELDOUT (host-/orchestrator-mediated SoD).
- generate: launch the DEVELOPER job (as ORCH_DEV) which builds/queries the Snowflake
  app and writes its artifact to the exchange stage. ORCH_DEV has NO access to the
  artifact schema → it never sees held-out (RBAC).
- run_tests / gate: run here as ORCH_PROJ (held-out-capable). pytest exit code ONLY.

Identity: the container is owned by ORCH_PROJ; to own a child it USE ROLEs ORCH_DEV /
ORCH_TEST (granted to ORCH_PROJ, downward-safe), then switches back. Exchange via the
mounted stage at /xchg.

Env (set by scripts/run.py): TASK_ID, CORE_SCHEMA, MAX_ITER, ORCH_IMAGE, ORCH_POOL,
XSTAGE, XSCHEMA, DEV_ROLE, TESTER_ROLE, SNOWFLAKE_WAREHOUSE, CORTEX_MODEL, AGENT_MAX_TURNS.
"""
import json
import os
import shutil
import subprocess
import sys
from typing import TypedDict

import snowflake.connector
from langgraph.graph import END, START, StateGraph

from gate import gate

TASK_ID = os.environ["TASK_ID"]
CORE = os.environ["CORE_SCHEMA"]
MAX_ITER = int(os.environ.get("MAX_ITER", "10"))
IMAGE = os.environ["ORCH_IMAGE"]
POOL = os.environ["ORCH_POOL"]
XSTAGE = os.environ["XSTAGE"]           # exchange stage fqn (ORCHESTRATOR.<ID>_XCHG.AGENT_STAGE)
XSCHEMA = os.environ["XSCHEMA"]         # exchange schema fqn (for child job names)
DEV_ROLE = os.environ["DEV_ROLE"]
TESTER_ROLE = os.environ["TESTER_ROLE"]
WAREHOUSE = os.environ.get("SNOWFLAKE_WAREHOUSE", "DEFAULT_WH")
XMOUNT = "/xchg"
_SAN = TASK_ID.replace("-", "_").upper()


class Ctx:
    conn = None
    artifact_schema = ""
    proj_role = ""        # the container's own role (ORCH_PROJ_<ID>)
    spec_text = ""


class State(TypedDict, total=False):
    iteration: int
    workdir: str
    last_output: str
    decision: str


def load_task() -> None:
    with open("/snowflake/session/token") as fh:
        token = fh.read()
    conn = snowflake.connector.connect(
        host=os.environ["SNOWFLAKE_HOST"], account=os.environ["SNOWFLAKE_ACCOUNT"],
        token=token, authenticator="oauth", warehouse=WAREHOUSE)
    cur = conn.cursor()
    cur.execute(f"SELECT project_id, spec_text FROM {CORE}.TASK_SPECS_CURRENT "
                "WHERE task_id = %s AND status = 'LOCKED'", (TASK_ID,))
    row = cur.fetchone()
    if not row:
        raise RuntimeError(f"no LOCKED task {TASK_ID} in {CORE}.TASK_SPECS")
    project_id, spec_text = row
    cur.execute(f"SELECT execution_role, artifact_schema FROM {CORE}.PROJECTS "
                "WHERE project_id = %s AND status = 'ACTIVE' "
                "ORDER BY created_at DESC LIMIT 1", (project_id,))
    proj_role, artifact_schema = cur.fetchone()
    cur.execute("SELECT CURRENT_ROLE()")
    print(f"running as role: {cur.fetchone()[0]} (expected {proj_role})", flush=True)
    Ctx.conn, Ctx.artifact_schema, Ctx.proj_role, Ctx.spec_text = (
        conn, artifact_schema, proj_role, spec_text)
    print(f"loaded task {TASK_ID} (project {project_id}); artifacts={artifact_schema}",
          flush=True)


def _child_spec(command: str, env_extra: dict) -> str:
    env_lines = "".join(f'\n        {k}: "{v}"' for k, v in env_extra.items())
    return f"""spec:
  containers:
    - name: main
      image: {IMAGE}
      command: {command}
      env:
        SNOWFLAKE_WAREHOUSE: "{WAREHOUSE}"
        CORTEX_MODEL: "{os.environ.get('CORTEX_MODEL', '')}"
        AGENT_MAX_TURNS: "{os.environ.get('AGENT_MAX_TURNS', '6')}"
        XCHG_MOUNT: {XMOUNT}{env_lines}
      volumeMounts:
        - name: xchg
          mountPath: {XMOUNT}
  volumes:
    - name: xchg
      source: "@{XSTAGE}"
"""


def _launch_child(role: str, job: str, command: str, env_extra: dict) -> str:
    """Nested EXECUTE JOB SERVICE as `role` (owns the child); synchronous. Returns log."""
    cur = Ctx.conn.cursor()
    spec = _child_spec(command, env_extra)
    cur.execute(f"DROP SERVICE IF EXISTS {job}")
    cur.execute(f"USE ROLE {role}")
    try:
        cur.execute(f"EXECUTE JOB SERVICE IN COMPUTE POOL {POOL} NAME = {job} "
                    f"FROM SPECIFICATION $${spec}$$")
    except Exception as exc:  # noqa: BLE001
        print(f"  child {job} raised: {type(exc).__name__}: {str(exc)[:200]}", flush=True)
    finally:
        cur.execute(f"USE ROLE {Ctx.proj_role}")
    try:
        log = cur.execute(
            f"SELECT SYSTEM$GET_SERVICE_LOGS('{job}', '0', 'main', 200)").fetchone()[0] or ""
    except Exception:  # noqa: BLE001
        log = ""
    cur.execute(f"DROP SERVICE IF EXISTS {job}")
    return log


def ensure_tests(state: State) -> dict:
    cur = Ctx.conn.cursor()
    cur.execute(f"SELECT COUNT(*) FROM {Ctx.artifact_schema}.TEST_VISIBLE "
                "WHERE task_id = %s", (TASK_ID,))
    if cur.fetchone()[0] > 0:
        print("ensure_tests: frozen tests already present", flush=True)
        return {}
    base = f"{XMOUNT}/{TASK_ID}/tester"
    os.makedirs(base, exist_ok=True)
    with open(f"{base}/_input.json", "w") as fh:
        json.dump({"spec": Ctx.spec_text}, fh)
    print("ensure_tests: launching TESTER job (ORCH_TEST)", flush=True)
    log = _launch_child(TESTER_ROLE, f"{XSCHEMA}.TESTERJOB_{_SAN}",
                        '["python", "-u", "/app/tester_job.py"]', {"TASK_ID": TASK_ID})
    print(log[-200:], flush=True)
    out = f"{base}/out"
    inserted = []
    for fn, tbl in (("test_visible.py", "TEST_VISIBLE"), ("test_heldout.py", "TEST_HELDOUT")):
        p = f"{out}/{fn}"
        if os.path.exists(p):
            content = open(p).read()
            cur.execute(f"DELETE FROM {Ctx.artifact_schema}.{tbl} WHERE task_id = %s", (TASK_ID,))
            cur.execute(f"INSERT INTO {Ctx.artifact_schema}.{tbl} "
                        "(task_id, filename, content) VALUES (%s,%s,%s)", (TASK_ID, fn, content))
            inserted.append(tbl)
    if "TEST_VISIBLE" not in inserted:
        raise RuntimeError("tester produced no test_visible.py")
    print(f"ensure_tests: inserted {inserted}", flush=True)
    return {}


def generate(state: State) -> dict:
    it = state["iteration"]
    base = f"{XMOUNT}/{TASK_ID}/iter-{it}"
    os.makedirs(base, exist_ok=True)
    with open(f"{base}/_input.json", "w") as fh:
        json.dump({"spec": Ctx.spec_text, "last_output": state.get("last_output")}, fh)
    log = _launch_child(DEV_ROLE, f"{XSCHEMA}.DEVJOB_{_SAN}_{it}",
                        '["python", "-u", "/app/agent_job.py"]',
                        {"TASK_ID": TASK_ID, "ITER": str(it)})
    out = f"{base}/out"
    meta = {}
    try:
        meta = json.load(open(f"{out}/_result.json"))
    except Exception:  # noqa: BLE001
        pass
    Ctx.conn.cursor().execute(
        f"INSERT INTO {Ctx.artifact_schema}.DEV_COMMENTS "
        "(task_id, iteration, author, comment) VALUES (%s,%s,%s,%s)",
        (TASK_ID, it, "developer",
         f"[{meta.get('source')}] {str(meta.get('summary',''))[:400]} "
         f"(turns={meta.get('num_turns')}, cost={meta.get('total_cost_usd')})"))
    print(f"[iter {it}] dev job done (source={meta.get('source')}, "
          f"is_error={meta.get('is_error')})", flush=True)
    return {"workdir": out}


def _pytest(paths, workdir, env):
    return subprocess.run([sys.executable, "-m", "pytest", *paths, "-q"],
                          cwd=workdir, capture_output=True, text=True, env=env)


def _materialize(table: str, dest: str) -> list:
    os.makedirs(dest, exist_ok=True)
    cur = Ctx.conn.cursor()
    cur.execute(f"SELECT filename, content FROM {Ctx.artifact_schema}.{table} "
                "WHERE task_id = %s", (TASK_ID,))
    paths = []
    for fn, content in cur.fetchall():
        p = os.path.join(dest, fn)
        with open(p, "w") as fh:
            fh.write(content or "")
        paths.append(p)
    return paths


def run_tests(state: State) -> dict:
    it = state["iteration"]
    workdir = state["workdir"]              # the DEV artifact tree (on the exchange mount)
    env = dict(os.environ)
    env["PYTHONPATH"] = workdir + os.pathsep + env.get("PYTHONPATH", "")
    # Held-out materialized to a CONTAINER-LOCAL dir (never the exchange) — the DEV job
    # ran in a separate container and never had it. Deleted right after.
    gate_dir = os.path.join("/tmp/gate", TASK_ID, f"iter-{it}")
    try:
        visible = _materialize("TEST_VISIBLE", os.path.join(gate_dir, "visible"))
        heldout = _materialize("TEST_HELDOUT", os.path.join(gate_dir, "heldout"))
        vis = _pytest(visible, workdir, env) if visible else None
        vis_ok = vis.returncode == 0 if vis else False
        held_ok = _pytest(heldout, workdir, env).returncode == 0 if heldout else True
        vis_out = (vis.stdout + vis.stderr) if vis else "no visible tests"
    finally:
        shutil.rmtree(gate_dir, ignore_errors=True)

    passed = vis_ok and held_ok
    Ctx.conn.cursor().execute(
        f"INSERT INTO {Ctx.artifact_schema}.TEST_RESULTS "
        "(task_id, iteration, tool, exit_code, passed, output) VALUES (%s,%s,%s,%s,%s,%s)",
        (TASK_ID, it, "pytest", 0 if passed else 1, passed,
         vis_out[:4000] + f"\n[held-out gate: {'PASS' if held_ok else 'FAIL'}]"))
    feedback = vis_out[:5000]
    if vis_ok and not held_ok:
        feedback += ("\n\nNote: additional hidden acceptance tests are still failing. "
                     "Re-examine the specification and edge cases.")
    print(f"[iter {it}] pytest visible={'ok' if vis_ok else 'fail'} "
          f"heldout={'ok' if held_ok else 'fail'} -> exit={0 if passed else 1}", flush=True)
    return {"last_output": feedback}


def gate_node(state: State) -> dict:
    g = gate(Ctx.conn.cursor(), Ctx.artifact_schema, TASK_ID, state["iteration"])
    print(f"[iter {state['iteration']}] gate -> {g['decision']} ({g['reason']})", flush=True)
    return {"decision": g["decision"]}


def route(state: State) -> str:
    if state["decision"] == "PASS":
        return "finalize_pass"
    if state["iteration"] + 1 >= MAX_ITER:
        return "finalize_stop"
    return "next_iter"


def next_iter(state: State) -> dict:
    return {"iteration": state["iteration"] + 1}


def finalize_pass(state: State) -> dict:
    Ctx.conn.cursor().execute(
        f"INSERT INTO {Ctx.artifact_schema}.RUNS (task_id, iteration, status, detail) "
        "VALUES (%s,%s,%s,%s)",
        (TASK_ID, state["iteration"], "DONE", f"passed at iteration {state['iteration']}"))
    print(f"RESULT: DONE at iteration {state['iteration']}", flush=True)
    return {}


def finalize_stop(state: State) -> dict:
    Ctx.conn.cursor().execute(
        f"INSERT INTO {Ctx.artifact_schema}.RUNS (task_id, iteration, status, detail) "
        "VALUES (%s,%s,%s,%s)",
        (TASK_ID, state["iteration"], "NEEDS_HUMAN",
         f"no PASS after {state['iteration'] + 1} iterations"))
    print(f"RESULT: NEEDS_HUMAN after {state['iteration'] + 1} iterations", flush=True)
    return {}


def build_graph():
    g = StateGraph(State)
    for name, fn in (("ensure_tests", ensure_tests), ("generate", generate),
                     ("run_tests", run_tests), ("gate", gate_node),
                     ("next_iter", next_iter), ("finalize_pass", finalize_pass),
                     ("finalize_stop", finalize_stop)):
        g.add_node(name, fn)
    g.add_edge(START, "ensure_tests")
    g.add_edge("ensure_tests", "generate")
    g.add_edge("generate", "run_tests")
    g.add_edge("run_tests", "gate")
    g.add_conditional_edges("gate", route, {
        "finalize_pass": "finalize_pass", "finalize_stop": "finalize_stop",
        "next_iter": "next_iter"})
    g.add_edge("next_iter", "generate")
    g.add_edge("finalize_pass", END)
    g.add_edge("finalize_stop", END)
    return g.compile()


def main() -> int:
    print("ORCH_BEGIN", flush=True)
    try:
        load_task()
        build_graph().invoke({"iteration": 0}, {"recursion_limit": MAX_ITER * 6 + 10})
    except Exception as exc:  # noqa: BLE001
        print(f"ORCH_FAIL: {type(exc).__name__}: {exc}", flush=True)
        return 1
    finally:
        print("ORCH_END", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
