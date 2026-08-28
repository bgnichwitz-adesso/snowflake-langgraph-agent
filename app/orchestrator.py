"""Paket 1.6 — the deterministic LangGraph orchestrator loop (runs in-container).

One container process runs the whole graph:

    load_task → generate → run_tests → gate ─┬─ PASS → finalize(done) → END
                  ↑                           └─ FAIL → (iter<MAX) loop
                  └───────────────────────────────────┘
                                            (iter≥MAX) → finalize(NEEDS_HUMAN) → END

- Task input comes from ORCHESTRATOR.CORE.TASK_SPECS (LEAD-owned, immutable).
- The loop assumes the project's execution role (USE ROLE) for all its work.
- Generated code is written to the mounted CODE_STAGE per iteration; reasoning
  to DEV_COMMENTS; pytest exit code + output to TEST_RESULTS; final outcome to
  RUNS. The gate (app/gate.py) decides on the exit code ONLY.
- Frozen tests (visible + held-out) are pre-staged under <task>/tests/. Claude
  sees only the visible tests (in the prompt); the gate runs both.

Env: TASK_ID, CORE_SCHEMA (e.g. ORCHESTRATOR.CORE), MOUNT_PATH (default
/workspace), MAX_ITER (default 10).
"""
import os
import shutil
import subprocess
import sys
from typing import TypedDict

import snowflake.connector
from langgraph.graph import END, START, StateGraph

import agent_worker
from gate import gate

MOUNT = os.environ.get("MOUNT_PATH", "/workspace")
AGENT_BASE = os.environ.get("AGENT_CWD_BASE", "/tmp/orch")  # local agent cwd root
TASK_ID = os.environ["TASK_ID"]
CORE = os.environ["CORE_SCHEMA"]
MAX_ITER = int(os.environ.get("MAX_ITER", "10"))


class Ctx:
    """Loaded once at startup: connection (role-scoped) + task metadata."""
    conn = None
    artifact_schema = ""
    execution_role = ""
    spec_text = ""
    task_dir = ""       # /workspace/<task> (mounted stage; for artifact audit copy)


class State(TypedDict, total=False):
    iteration: int
    workdir: str        # local dir where the agent wrote this iteration's files
    last_output: str
    decision: str


def load_task() -> None:
    with open("/snowflake/session/token") as fh:
        token = fh.read()
    conn = snowflake.connector.connect(
        host=os.environ["SNOWFLAKE_HOST"],
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        token=token,
        authenticator="oauth",
        warehouse=os.environ.get("SNOWFLAKE_WAREHOUSE", "DEFAULT_WH"),
    )
    cur = conn.cursor()
    # Read input as the owner role, resolve the project + its execution role.
    cur.execute(
        f"SELECT project_id, spec_text FROM {CORE}.TASK_SPECS_CURRENT "
        "WHERE task_id = %s AND status = 'LOCKED'",
        (TASK_ID,),
    )
    row = cur.fetchone()
    if not row:
        raise RuntimeError(f"no LOCKED task {TASK_ID} in {CORE}.TASK_SPECS")
    project_id, spec_text = row
    cur.execute(
        f"SELECT execution_role, artifact_schema FROM {CORE}.PROJECTS "
        "WHERE project_id = %s AND status = 'ACTIVE' "
        "ORDER BY created_at DESC LIMIT 1",
        (project_id,),
    )
    execution_role, artifact_schema = cur.fetchone()
    # The job-service is created/owned by the project execution role (Paket
    # 1.6b), so the container session already runs as it — no USE ROLE needed.
    cur.execute("SELECT CURRENT_ROLE()")
    current_role = cur.fetchone()[0]
    print(f"running as role: {current_role} (expected {execution_role})", flush=True)

    Ctx.conn = conn
    Ctx.artifact_schema = artifact_schema
    Ctx.execution_role = execution_role
    Ctx.spec_text = spec_text
    Ctx.task_dir = os.path.join(MOUNT, TASK_ID)
    print(f"loaded task {TASK_ID} (project {project_id}); "
          f"role={execution_role}; artifacts={artifact_schema}", flush=True)


def generate(state: State) -> dict:
    it = state["iteration"]
    # Agent works in a LOCAL dir it fully controls; it never sees the frozen
    # tests (they live in Snowflake tables, materialized only at gate time).
    cwd = os.path.join(AGENT_BASE, TASK_ID, f"iter-{it}")
    res = agent_worker.run(spec=Ctx.spec_text,
                           last_output=state.get("last_output"), cwd=cwd)
    # Persist the produced tree to the stage for audit (best-effort, non-fatal).
    try:
        shutil.copytree(cwd, os.path.join(Ctx.task_dir, f"iter-{it}"),
                        dirs_exist_ok=True)
    except Exception as exc:  # noqa: BLE001
        print(f"[iter {it}] stage copy warn: {exc}", flush=True)
    usage = res.get("usage") or {}
    tokens = usage.get("total_tokens") or usage.get("output_tokens")
    cur = Ctx.conn.cursor()
    cur.execute(
        f"INSERT INTO {Ctx.artifact_schema}.DEV_COMMENTS "
        "(task_id, iteration, author, comment) VALUES (%s,%s,%s,%s)",
        (TASK_ID, it, "developer",
         f"[{res['source']}] {res['summary'][:400]} "
         f"(turns={res.get('num_turns')}, tokens={tokens}, "
         f"cost={res.get('total_cost_usd')})"),
    )
    print(f"[iter {it}] agent done (source={res['source']}, "
          f"is_error={res['is_error']})", flush=True)
    return {"workdir": cwd}


def _pytest(paths, workdir, env):
    return subprocess.run(
        [sys.executable, "-m", "pytest", *paths, "-q"],
        cwd=workdir, capture_output=True, text=True, env=env,
    )


def _materialize(table: str, dest: str) -> list:
    """Write frozen tests from a Snowflake table into a local temp dir."""
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
    workdir = state["workdir"]              # the agent's local output tree
    env = dict(os.environ)
    env["PYTHONPATH"] = workdir + os.pathsep + env.get("PYTHONPATH", "")

    # Frozen tests come from Snowflake tables (NOT the mounted stage, NOT the
    # agent cwd) into a transient local dir that is deleted right after — so the
    # developer agent never has held-out tests on disk. VISIBLE feedback only.
    gate_dir = os.path.join("/tmp/gate", TASK_ID, f"iter-{it}")
    try:
        visible = _materialize("TEST_VISIBLE", os.path.join(gate_dir, "visible"))
        heldout = _materialize("TEST_HELDOUT", os.path.join(gate_dir, "heldout"))

        vis = _pytest(visible, workdir, env) if visible else None
        vis_ok = vis.returncode == 0 if vis else False
        held_ok = _pytest(heldout, workdir, env).returncode == 0 if heldout else True
        vis_out = ((vis.stdout + vis.stderr) if vis else "no visible tests")
    finally:
        shutil.rmtree(gate_dir, ignore_errors=True)   # held-out never lingers

    passed = vis_ok and held_ok
    exit_code = 0 if passed else 1
    stored = (vis_out[:4000]
              + f"\n[held-out gate: {'PASS' if held_ok else 'FAIL'}]")
    Ctx.conn.cursor().execute(
        f"INSERT INTO {Ctx.artifact_schema}.TEST_RESULTS "
        "(task_id, iteration, tool, exit_code, passed, output) "
        "VALUES (%s,%s,%s,%s,%s,%s)",
        (TASK_ID, it, "pytest", exit_code, passed, stored),
    )
    # Feedback = visible only; if only held-out failed, a generic hint (no details).
    feedback = vis_out[:5000]
    if vis_ok and not held_ok:
        feedback += ("\n\nNote: additional hidden acceptance tests are still "
                     "failing. Re-examine the specification and edge cases.")
    print(f"[iter {it}] pytest visible={'ok' if vis_ok else 'fail'} "
          f"heldout={'ok' if held_ok else 'fail'} -> exit={exit_code}", flush=True)
    return {"last_output": feedback}


def gate_node(state: State) -> dict:
    g = gate(Ctx.conn.cursor(), Ctx.artifact_schema, TASK_ID, state["iteration"])
    print(f"[iter {state['iteration']}] gate -> {g['decision']} ({g['reason']})",
          flush=True)
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
        (TASK_ID, state["iteration"], "DONE",
         f"passed at iteration {state['iteration']}"),
    )
    print(f"RESULT: DONE at iteration {state['iteration']}", flush=True)
    return {}


def finalize_stop(state: State) -> dict:
    Ctx.conn.cursor().execute(
        f"INSERT INTO {Ctx.artifact_schema}.RUNS (task_id, iteration, status, detail) "
        "VALUES (%s,%s,%s,%s)",
        (TASK_ID, state["iteration"], "NEEDS_HUMAN",
         f"no PASS after {state['iteration'] + 1} iterations; "
         f"last output: {state.get('last_output','')[:500]}"),
    )
    print(f"RESULT: NEEDS_HUMAN after {state['iteration'] + 1} iterations",
          flush=True)
    return {}


def build_graph():
    g = StateGraph(State)
    g.add_node("generate", generate)
    g.add_node("run_tests", run_tests)
    g.add_node("gate", gate_node)
    g.add_node("next_iter", next_iter)
    g.add_node("finalize_pass", finalize_pass)
    g.add_node("finalize_stop", finalize_stop)
    g.add_edge(START, "generate")
    g.add_edge("generate", "run_tests")
    g.add_edge("run_tests", "gate")
    g.add_conditional_edges("gate", route, {
        "finalize_pass": "finalize_pass",
        "finalize_stop": "finalize_stop",
        "next_iter": "next_iter",
    })
    g.add_edge("next_iter", "generate")
    g.add_edge("finalize_pass", END)
    g.add_edge("finalize_stop", END)
    return g.compile()


def main() -> int:
    print("ORCH_BEGIN", flush=True)
    try:
        load_task()
        # recursion budget: each iteration is generate+test+gate(+next) ~4 steps
        graph = build_graph()
        graph.invoke({"iteration": 0}, {"recursion_limit": MAX_ITER * 6 + 10})
    except Exception as exc:  # noqa: BLE001
        print(f"ORCH_FAIL: {type(exc).__name__}: {exc}", flush=True)
        return 1
    finally:
        print("ORCH_END", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
