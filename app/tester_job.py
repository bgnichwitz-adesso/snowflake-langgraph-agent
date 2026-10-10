"""1.8 — TESTER-agent SPCS job entrypoint (runs AS ORCH_TEST_<ID>).

Separation of Duties: a DIFFERENT identity than the developer AUTHORS the frozen tests
from the spec. Runs in its own SPCS job (own OAuth token, exempt from the network
policy). Tool-sandboxed (file tools + SQL to inspect the project DB; no Bash).

Exchange via the mounted stage (/xchg):
  in : /xchg/<task>/tester/_input.json   {"spec": ...}         (host-written)
  out: /xchg/<task>/tester/out/          test_visible.py, test_heldout.py, manifest.json

The host then inserts the two files into TEST_VISIBLE / TEST_HELDOUT (host-mediated,
so the tester never writes the authoritative tables directly). Env: TASK_ID, XCHG_MOUNT.
"""
import json
import os
import shutil

import agent_worker

XCHG = os.environ.get("XCHG_MOUNT", "/xchg")
TASK_ID = os.environ["TASK_ID"]

TESTER_SYSTEM = (
    "You are a QA engineer. Given a task specification, write pytest tests that verify "
    "a correct solution. Produce EXACTLY two files IN THE CURRENT WORKING DIRECTORY:\n"
    "- test_visible.py : representative tests the developer is allowed to see.\n"
    "- test_heldout.py : additional HIDDEN acceptance tests covering edge cases and "
    "corner behaviours NOT obvious from the spec (the developer never sees these).\n"
    "Import the solution exactly as the spec dictates (module/function names). Use plain "
    "pytest functions (def test_*). Do NOT write the solution/implementation itself — "
    "ONLY the two test files. Also write manifest.json with "
    '{"summary","files","ready"}.'
)
TESTER_CLOSING = "\nWrite test_visible.py and test_heldout.py now, then manifest.json."


def main() -> int:
    print("TESTER_JOB_BEGIN", flush=True)
    base = os.path.join(XCHG, TASK_ID, "tester")
    with open(os.path.join(base, "_input.json")) as fh:
        spec = json.load(fh)["spec"]

    cwd = f"/tmp/tester/{TASK_ID}"
    res = agent_worker.run(spec=spec, last_output=None, cwd=cwd,
                           system=TESTER_SYSTEM, closing=TESTER_CLOSING)

    out = os.path.join(base, "out")
    os.makedirs(out, exist_ok=True)
    for fn in ("test_visible.py", "test_heldout.py", "manifest.json"):
        src = os.path.join(cwd, fn)
        if os.path.exists(src):
            shutil.copy(src, os.path.join(out, fn))
    have = sorted(f for f in ("test_visible.py", "test_heldout.py")
                  if os.path.exists(os.path.join(out, f)))
    print(f"TESTER_JOB_DONE source={res.get('source')} files={have}", flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"TESTER_JOB_FAIL: {type(exc).__name__}: {exc}", flush=True)
        raise SystemExit(1)
