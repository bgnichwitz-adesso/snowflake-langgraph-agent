"""M3 — agentic DEVELOPER worker (Cortex Code SDK).

Replaces the one-shot cortex_complete in the loop's generate() node. The agent
writes/iterates files itself into `cwd` (a LOCAL dir — the orchestrator persists
the tree to the stage separately, so the agent never sees held-out tests) and
returns a schema-validated artifact {summary, entry_point, files, ready}.

Artifact source: ResultMessage.structured_output (via output_format/--json-schema)
with a manifest.json fallback (CLI-version independent). Sync entry: run().
"""
import asyncio
import json
import os

from agent_env import bootstrap_agent_auth

MODEL = os.environ.get("CORTEX_MODEL", "claude-sonnet-4-6")
MAX_TURNS = int(os.environ.get("AGENT_MAX_TURNS", "6"))

# --- Tool sandbox (gate integrity) -------------------------------------------
# The developer agent must not be able to read the held-out tests. Those live in
# a Snowflake table (no SQL grant to the agent's role) AND the gate's OAuth token
# sits on the shared container filesystem at /snowflake/session/token — a
# filesystem-capable agent could read that token and escalate. So we scope the
# agent's TOOLS: file tools only, every call path-jailed to its cwd; no shell, no
# SQL, no network. This closes both the SQL-read and the token-file-read vectors
# in a single container (see docs migration M4). A least-priv PAT connection is
# the documented next-layer hardening for when real tasks need shell/SQL.
# File tools (cwd-jailed) + the built-in Snowflake SQL tool. The SQL tool (name
# "SQL" in cortex v1.1.66; its input is {action, resource:<query>}, no path) runs
# under the agent's OWN connection identity. Under M6/B that identity is the
# least-priv ORCH_APP_<ID> role (PAT), which has NO grant on the orchestrator test
# tables — so RBAC, not query inspection, keeps held-out unreadable. Bash stays OUT
# (it could `cat /snowflake/session/token` = the gate identity and escalate).
_ALLOWED_TOOLS = {"Read", "Write", "Edit", "MultiEdit", "LS", "Glob", "Grep", "SQL"}
_PATH_KEYS = ("file_path", "path", "notebook_path")
_FORBIDDEN_SUBSTR = ("/snowflake",)  # never let a path reach the session token

ARTIFACT_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "entry_point": {"type": "string"},
        "files": {"type": "array", "items": {"type": "string"}},
        "ready": {"type": "boolean"},
    },
    "required": ["summary", "ready"],
}

SYSTEM = (
    "You are a senior developer. Build a working solution IN THE CURRENT WORKING "
    "DIRECTORY that passes the given visible tests. You may create multiple files. "
    "Do NOT create any test files (nothing named test_*.py) — tests are provided and "
    "frozen. When finished, ALSO write a file named manifest.json in the cwd with keys "
    '{"summary","entry_point","files","ready"}.'
)


def _build_prompt(spec: str, last_output) -> str:
    p = f"{SYSTEM}\n\n## Task specification (includes the visible tests)\n{spec}\n"
    if last_output:
        p += ("\n## Your previous attempt FAILED these tests — fix the code:\n"
              f"{str(last_output)[:3000]}\n")
    p += "\nBuild the solution now, then write manifest.json."
    return p


def _collect(result, cwd: str) -> dict:
    structured = getattr(result, "structured_output", None) if result else None
    source = "structured_output" if structured else "none"
    if not structured:
        mpath = os.path.join(cwd, "manifest.json")
        if os.path.exists(mpath):
            try:
                structured = json.load(open(mpath))
                source = "manifest.json"
            except Exception:  # noqa: BLE001
                structured = None
    summary = structured.get("summary", "") if isinstance(structured, dict) else ""
    if not summary and result is not None:
        summary = (getattr(result, "result", "") or "")[:500]
    return {
        "artifact": structured,
        "summary": summary or "(no summary)",
        "usage": getattr(result, "usage", None) if result else None,
        "total_cost_usd": getattr(result, "total_cost_usd", None) if result else None,
        "num_turns": getattr(result, "num_turns", None) if result else None,
        "is_error": getattr(result, "is_error", True) if result else True,
        "source": source,
        "cwd": cwd,
    }


# Sandbox mode: "on" (enforce, default) or "observe" (log-only, allow all — used
# ONLY by the leak-control proof to see whether an UNBLOCKED agent would actually
# reach held-out; never for real runs).
SANDBOX_MODE = os.environ.get("AGENT_SANDBOX", "on")


def _make_guard(cwd: str, mode: str = None):
    """Per-tool allow/deny: file tools only, every path jailed to cwd.

    mode="observe" logs the same DENY/allow decisions but ALLOWS everything, so a
    control run can observe an unblocked agent's natural tool use (does it try to
    read held-out?). mode="on" (default) enforces.
    """
    from cortex_code_agent_sdk import PermissionResultAllow, PermissionResultDeny

    mode = mode or SANDBOX_MODE
    observe = mode == "observe"
    root = os.path.realpath(cwd)

    def _within(p: str) -> bool:
        if any(s in p for s in _FORBIDDEN_SUBSTR):
            return False
        ap = os.path.realpath(p if os.path.isabs(p) else os.path.join(root, p))
        return ap == root or ap.startswith(root + os.sep)

    def _deny(tool_name, reason, detail):
        tag = "WOULD-DENY(observe)" if observe else "DENY"
        print(f"[guard] {tag} tool={tool_name} reason={reason} {detail}", flush=True)
        if observe:
            return PermissionResultAllow()
        return PermissionResultDeny(message=f"{reason}: {tool_name}")

    async def can_use_tool(tool_name, tool_input, _ctx):
        if tool_name not in _ALLOWED_TOOLS:
            return _deny(tool_name, "not-in-allowlist", f"input={str(tool_input)[:160]}")
        for k in _PATH_KEYS:
            v = tool_input.get(k) if isinstance(tool_input, dict) else None
            if isinstance(v, str) and v and not _within(v):
                return _deny(tool_name, "path-outside-cwd", f"path={v}")
        print(f"[guard] allow tool={tool_name}", flush=True)
        return PermissionResultAllow()

    return can_use_tool


async def _run_async(prompt: str, cwd: str) -> dict:
    from cortex_code_agent_sdk import CortexCodeAgentOptions, query

    conn_name, agent_env = bootstrap_agent_auth()
    os.makedirs(cwd, exist_ok=True)
    opts = dict(
        cwd=cwd,
        connection=conn_name,
        # SDK-managed permissions: every tool call routes through _make_guard
        # (allowlist + cwd path-jail). No bypass — the guard is the hard gate.
        permission_mode="default",
        can_use_tool=_make_guard(cwd),
        # belt: hard-deny shell at the flag level too (skipped in observe control)
        disallowed_tools=([] if SANDBOX_MODE == "observe" else ["Bash"]),
        max_turns=MAX_TURNS,
        env=agent_env,
        extra_args={"no-auto-update": None},
        output_format={"type": "json_schema", "schema": ARTIFACT_SCHEMA},
    )
    if MODEL:
        opts["model"] = MODEL
    options = CortexCodeAgentOptions(**opts)

    result = None
    async for message in query(prompt=prompt, options=options):
        if type(message).__name__ == "ResultMessage":
            result = message
    return _collect(result, cwd)


def run(spec: str, last_output=None, cwd: str = "/tmp/agent_work") -> dict:
    """Sync entry for the LangGraph generate() node."""
    return asyncio.run(_run_async(_build_prompt(spec, last_output), cwd))
