"""M4 guard unit proof — the agent tool-sandbox DENY logic (local, no credits).

Directly exercises `agent_worker._make_guard`'s `can_use_tool` callback: proves it
DENIES the held-out read vectors (non-file tools like Bash/SQL, the SPCS session
token, paths outside cwd, and `..` traversal into the gate's held-out dir) and
ALLOWS only file tools inside cwd. This is the deterministic complement to
`p_m4_leak.py` (which shows, live in-container, that the guard is actually wired
and that a held-out-only value stays unreachable → NEEDS_HUMAN).
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))
from agent_worker import _make_guard  # noqa: E402

CWD = "/tmp/orch/task-x/iter-0"

# (tool, input, expected_behavior, why)
CASES = [
    ("Bash",       {"command": "cat /snowflake/session/token"}, "deny", "shell not in allowlist"),
    ("ExecuteSql", {"query": "SELECT content FROM ORCHESTRATOR.DEMO.TEST_HELDOUT"}, "deny", "SQL not in allowlist"),
    ("Read",       {"file_path": "/snowflake/session/token"}, "deny", "reads the gate OAuth token"),
    ("Read",       {"file_path": "../../../etc/passwd"}, "deny", "absolute-ish escape"),
    ("Read",       {"file_path": CWD + "/../heldout/test_heldout.py"}, "deny", ".. traversal into held-out dir"),
    ("Glob",       {"path": "/workspace/task-x/tests"}, "deny", "reaches the mounted stage"),
    ("WebFetch",   {"url": "http://x"}, "deny", "network not in allowlist"),
    ("Write",      {"file_path": CWD + "/solution.py"}, "allow", "legit file write in cwd"),
    ("Read",       {"file_path": CWD + "/solution.py"}, "allow", "legit read in cwd"),
    ("Glob",       {"path": CWD}, "allow", "legit glob in cwd"),
    ("Edit",       {"file_path": CWD + "/mathutil.py"}, "allow", "legit edit in cwd"),
]


async def _run() -> bool:
    guard = _make_guard(CWD)
    print(f"cwd jail = {CWD}\n")
    ok = True
    for name, inp, expect, why in CASES:
        beh = getattr(await guard(name, inp, None), "behavior", "?")
        good = beh == expect
        ok = ok and good
        print(f"  [{'OK' if good else 'XXX'}] {name:11} -> {beh:5} "
              f"(expect {expect}) — {why}")
    return ok


def main() -> int:
    ok = asyncio.run(_run())
    print(f"\n{'PASS — guard denies held-out vectors, allows only cwd file tools' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
