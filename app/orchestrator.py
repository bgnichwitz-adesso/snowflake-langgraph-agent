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

from cortex_client import cortex_complete
from gate import gate

MOUNT = os.environ.get("MOUNT_PATH", "/workspace")
TASK_ID = os.environ["TASK_ID"]
CORE = os.environ["CORE_SCHEMA"]
MAX_ITER = int(os.environ.get("MAX_ITER", "10"))

SYSTEM = (
    "You are a senior Python developer. You are given a task and the visible "
    "tests it must pass. Return ONLY the full content of solution.py — no "
    "explanation, no markdown fences. The code must be importable and define "
    "exactly what the tests need."
)


class Ctx:
    """Loaded once at startup: connection (role-scoped) + task metadata."""
    conn = None
    artifact_schema = ""
    execution_role = ""
    spec_text = ""
    task_dir = ""       # /workspace/<task>
    tests_dir = ""      # /workspace/<task>/tests


class State(TypedDict, total=False):
    iteration: int
    code: str
    last_output: str
    decision: str


def _extract_code(text: str) -> str:
    t = text.strip()
    if "```" in t:
        block = t.split("```")[1]
        if block.lower().startswith("python"):
            block = block[len("python"):]
        return block.strip() + "\n"
    return t + "\n"


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
    # NOTE (Paket 1.6b): the loop will run under the project execution role once
    # the service is created/owned by ORCH_RUNNER→ORCH_PROJ_<ID> (needs pool/
    # image/stage + create-service grants). For 1.6 we run as the service owner
    # to prove the loop mechanics; role-scoping is its own package.
    # cur.execute(f"USE ROLE {execution_role}")

    Ctx.conn = conn
    Ctx.artifact_schema = artifact_schema
    Ctx.execution_role = execution_role
    Ctx.spec_text = spec_text
    Ctx.task_dir = os.path.join(MOUNT, TASK_ID)
    Ctx.tests_dir = os.path.join(Ctx.task_dir, "tests")
    print(f"loaded task {TASK_ID} (project {project_id}); "
          f"role={execution_role}; artifacts={artifact_schema}", flush=True)


def generate(state: State) -> dict:
    it = state["iteration"]
    messages = [{"role": "system", "content": SYSTEM},
                {"role": "user", "content": Ctx.spec_text}]
    if state.get("last_output"):
        messages.append({
            "role": "user",
            "content": "Your previous attempt failed these tests. Fix it. "
                       f"Test output:\n{state['last_output'][:3000]}",
        })
    result = cortex_complete(messages, temperature=0, conn=Ctx.conn)
    code = _extract_code(result["text"])
    cur = Ctx.conn.cursor()
    cur.execute(
        f"INSERT INTO {Ctx.artifact_schema}.DEV_COMMENTS "
        "(task_id, iteration, author, comment) VALUES (%s,%s,%s,%s)",
        (TASK_ID, it, "developer",
         f"generated solution ({result['usage'].get('total_tokens')} tokens)"),
    )
    print(f"[iter {it}] generated {len(code)} chars", flush=True)
    return {"code": code}


def run_tests(state: State) -> dict:
    it = state["iteration"]
    workdir = os.path.join(Ctx.task_dir, f"iter-{it}")
    os.makedirs(workdir, exist_ok=True)
    with open(os.path.join(workdir, "solution.py"), "w") as fh:
        fh.write(state["code"])
    # copy the frozen tests (visible + held-out) next to the solution
    for fn in os.listdir(Ctx.tests_dir):
        if fn.endswith(".py"):
            shutil.copy(os.path.join(Ctx.tests_dir, fn), workdir)
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q"],
        cwd=workdir, capture_output=True, text=True,
    )
    output = (proc.stdout + proc.stderr)[:5000]
    cur = Ctx.conn.cursor()
    cur.execute(
        f"INSERT INTO {Ctx.artifact_schema}.TEST_RESULTS "
        "(task_id, iteration, tool, exit_code, passed, output) "
        "VALUES (%s,%s,%s,%s,%s,%s)",
        (TASK_ID, it, "pytest", proc.returncode, proc.returncode == 0, output),
    )
    print(f"[iter {it}] pytest exit={proc.returncode}", flush=True)
    return {"last_output": output}


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
