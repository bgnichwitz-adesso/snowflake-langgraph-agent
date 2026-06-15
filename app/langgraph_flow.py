"""Package 5 — minimal LangGraph flow with a single node that calls Claude via
Cortex (internal OAuth path) and returns the response.

Scope: proof of concept only. No loop, no test gate, no real tasks.
Run inside the SPCS container. Prints the graph output for log verification.
"""
import os
import sys
from typing import TypedDict

import snowflake.connector
from langgraph.graph import END, START, StateGraph

MODEL = "claude-sonnet-4-6"
TOKEN_PATH = "/snowflake/session/token"


class State(TypedDict):
    prompt: str
    response: str


def _cortex_complete(prompt: str) -> str:
    with open(TOKEN_PATH) as fh:
        token = fh.read()
    conn = snowflake.connector.connect(
        host=os.environ["SNOWFLAKE_HOST"],
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        token=token,
        authenticator="oauth",
        warehouse=os.environ.get("SNOWFLAKE_WAREHOUSE", "DEFAULT_WH"),
    )
    cur = conn.cursor()
    cur.execute("SELECT SNOWFLAKE.CORTEX.COMPLETE(%s, %s)", (MODEL, prompt))
    return cur.fetchone()[0]


def call_claude(state: State) -> dict:
    return {"response": _cortex_complete(state["prompt"])}


def build_graph():
    builder = StateGraph(State)
    builder.add_node("call_claude", call_claude)
    builder.add_edge(START, "call_claude")
    builder.add_edge("call_claude", END)
    return builder.compile()


def main() -> int:
    prompt = sys.argv[1] if len(sys.argv) > 1 else "say: SYSTEM OK"
    try:
        graph = build_graph()
        result = graph.invoke({"prompt": prompt})
    except Exception as exc:  # noqa: BLE001
        print(f"GRAPH_FAIL: {type(exc).__name__}: {exc}", flush=True)
        return 1
    print("GRAPH_OUTPUT_BEGIN", flush=True)
    print(result.get("response"), flush=True)
    print("GRAPH_OUTPUT_END", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
