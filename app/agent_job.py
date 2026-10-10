"""M6/B — developer-agent SPCS job entrypoint (runs AS ORCH_DEV_<ID>).

This is the "generate" step of the Form-B loop, running in its OWN SPCS job owned by
the developer role. It authenticates with that job's internal SPCS OAuth token
(= ORCH_DEV: project-DB build rights + CORTEX, NO orchestrator artifact schema), so
the agent can run SQL against the project DB but cannot reach held-out tests (RBAC).

Exchange via the mounted dedicated stage (ORCHESTRATOR.<ID>_XCHG.AGENT_STAGE at /xchg):
  in : /xchg/<task>/iter-<N>/_input.json      {"spec": ..., "last_output": ...}  (host-written)
  out: /xchg/<task>/iter-<N>/out/<tree>        agent artifact tree + _result.json

The agent stays tool-sandboxed (agent_worker: file tools + the SQL tool, no Bash).
Env: TASK_ID, ITER, XCHG_MOUNT (default /xchg).
"""
import json
import os
import shutil
import sys

import agent_worker

XCHG = os.environ.get("XCHG_MOUNT", "/xchg")
TASK_ID = os.environ["TASK_ID"]
ITER = os.environ.get("ITER", "0")


def main() -> int:
    print("AGENT_JOB_BEGIN", flush=True)
    base = os.path.join(XCHG, TASK_ID, f"iter-{ITER}")
    with open(os.path.join(base, "_input.json")) as fh:
        inp = json.load(fh)
    spec = inp["spec"]
    last_output = inp.get("last_output")

    cwd = f"/tmp/orch/{TASK_ID}/iter-{ITER}"
    res = agent_worker.run(spec=spec, last_output=last_output, cwd=cwd)

    # publish the produced tree + a result manifest to the exchange stage (mounted
    # read-write; writes persist to the stage for the host loop to GET).
    out = os.path.join(base, "out")
    os.makedirs(out, exist_ok=True)
    try:
        shutil.copytree(cwd, out, dirs_exist_ok=True)
    except Exception as exc:  # noqa: BLE001
        print(f"copy-to-exchange warn: {exc}", flush=True)
    meta = {k: res.get(k) for k in
            ("source", "summary", "is_error", "num_turns", "total_cost_usd")}
    meta["artifact"] = res.get("artifact")
    with open(os.path.join(out, "_result.json"), "w") as fh:
        json.dump(meta, fh)

    print(f"AGENT_JOB_DONE source={res.get('source')} "
          f"is_error={res.get('is_error')}", flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"AGENT_JOB_FAIL: {type(exc).__name__}: {exc}", flush=True)
        raise SystemExit(1)
