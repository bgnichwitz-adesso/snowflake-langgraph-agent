"""M6/B — host/runner-driven deterministic loop (Form B).

Replaces the in-container LangGraph loop for the agentic path. Each iteration:
  generate : launch a DEV SPCS job OWNED BY ORCH_DEV_<ID> (chain RUNNER->ORCH_DEV)
             that runs the tool-sandboxed agent as ORCH_DEV (project-DB SQL, no
             held-out) and writes its artifact to the exchange stage.
  collect  : GET the artifact tree from the exchange stage.
  gate     : as ORCH_PROJ/admin (held-out-capable), materialize visible+held-out
             from the per-project tables and run pytest; decide on the exit code ONLY.
  record   : append TEST_RESULTS + DEV_COMMENTS; on PASS -> RUNS=DONE, else loop with
             VISIBLE-only feedback; after MAX_ITER -> RUNS=NEEDS_HUMAN.

Held-out never reaches the developer: ORCH_DEV has no access to the artifact schema
(RBAC), and the gate runs here, not in the dev job. Usage:
  run_loop.py --task <task_id> [--tag latest] [--max-iter 3]
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile

import config
from sf import connect

ADMIN = "ACCOUNTADMIN"


def _materialize(cur, art, table, task_id, dest):
    os.makedirs(dest, exist_ok=True)
    cur.execute(f"SELECT filename, content FROM {art}.{table} WHERE task_id = %s",
                (task_id,))
    paths = []
    for fn, content in cur.fetchall():
        p = os.path.join(dest, fn)
        with open(p, "w") as fh:
            fh.write(content or "")
        paths.append(p)
    return paths


def _pytest(paths, workdir, env):
    return subprocess.run([sys.executable, "-m", "pytest", *paths, "-q"],
                          cwd=workdir, capture_output=True, text=True, env=env)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", required=True)
    ap.add_argument("--tag", default="latest")
    ap.add_argument("--max-iter", type=int, default=3)
    a = ap.parse_args()
    task = a.task
    pool = config.POOL

    try:
        with connect() as conn:
            cur = conn.cursor()
            cur.execute("SELECT CURRENT_USER()")
            user = cur.fetchone()[0]
            cur.execute(f"GRANT ROLE {config.RUNNER_ROLE} TO USER {user}")  # idempotent

            # load task + project
            cur.execute(f"SELECT project_id, spec_text FROM "
                        f"{config.DATABASE}.{config.SCHEMA}.TASK_SPECS_CURRENT "
                        "WHERE task_id = %s AND status = 'LOCKED'", (task,))
            row = cur.fetchone()
            if not row:
                raise RuntimeError(f"no LOCKED task {task}")
            project_id, spec_text = row
            art = config.artifact_schema(project_id)
            dev = config.dev_role(project_id)
            xstage = config.exchange_stage(project_id)
            xschema = config.exchange_schema(project_id)
            print(f"task {task} (project {project_id}); dev={dev}; art={art}", flush=True)

            last_output = None
            status = None
            for it in range(a.max_iter):
                print(f"\n=== iter {it} ===", flush=True)
                workdir = tempfile.mkdtemp(prefix=f"loop_{task}_{it}_")

                # 1) write _input.json and PUT to the exchange stage
                local_in = os.path.join(workdir, "_input.json")
                with open(local_in, "w") as fh:
                    json.dump({"spec": spec_text, "last_output": last_output}, fh)
                stage_dir = f"@{xstage}/{task}/iter-{it}"
                cur.execute(f"REMOVE {stage_dir}")
                cur.execute(f"PUT 'file://{local_in}' {stage_dir}/ "
                            "AUTO_COMPRESS=FALSE OVERWRITE=TRUE")

                # 2) launch the DEV job as ORCH_DEV (synchronous)
                job = f"{xschema}.DEVJOB_{task.replace('-', '_').upper()}_{it}"
                spec = f"""
spec:
  containers:
    - name: main
      image: {config.spec_image_path(a.tag)}
      command: ["python", "-u", "/app/agent_job.py"]
      env:
        TASK_ID: {task}
        ITER: "{it}"
        XCHG_MOUNT: /xchg
        SNOWFLAKE_WAREHOUSE: "{config.WAREHOUSE}"
        CORTEX_MODEL: "{config.CORTEX_MODEL}"
        AGENT_MAX_TURNS: "{config.AGENT_MAX_TURNS}"
      volumeMounts:
        - name: xchg
          mountPath: /xchg
  volumes:
    - name: xchg
      source: "@{xstage}"
"""
                cur.execute(f"DROP SERVICE IF EXISTS {job}")
                cur.execute(f"USE ROLE {config.RUNNER_ROLE}")
                cur.execute(f"USE ROLE {dev}")
                try:
                    cur.execute(f"EXECUTE JOB SERVICE IN COMPUTE POOL {pool} "
                                f"NAME = {job} FROM SPECIFICATION $${spec}$$")
                except Exception as exc:  # noqa: BLE001
                    print(f"  dev job raised: {type(exc).__name__}: {str(exc)[:160]}",
                          flush=True)
                cur.execute(f"USE ROLE {ADMIN}")
                cur.execute(f"SELECT SYSTEM$GET_SERVICE_LOGS('{job}', '0', 'main', 500)")
                print((cur.fetchone()[0] or "")[-800:], flush=True)

                # 3) collect the artifact tree from the exchange stage
                art_dir = os.path.join(workdir, "artifact")
                os.makedirs(art_dir, exist_ok=True)
                cur.execute(f"GET {stage_dir}/out/ 'file://{art_dir}/'")
                cur.execute(f"DROP SERVICE IF EXISTS {job}")

                # 4) gate (as admin: held-out-capable) — pytest on the artifact tree
                env = dict(os.environ)
                env["PYTHONPATH"] = art_dir + os.pathsep + env.get("PYTHONPATH", "")
                gate_dir = os.path.join(workdir, "gate")
                try:
                    vis = _materialize(cur, art, "TEST_VISIBLE", task,
                                       os.path.join(gate_dir, "visible"))
                    held = _materialize(cur, art, "TEST_HELDOUT", task,
                                        os.path.join(gate_dir, "heldout"))
                    rv = _pytest(vis, art_dir, env) if vis else None
                    vis_ok = rv.returncode == 0 if rv else False
                    held_ok = (_pytest(held, art_dir, env).returncode == 0
                               if held else True)
                    vis_out = (rv.stdout + rv.stderr) if rv else "no visible tests"
                finally:
                    shutil.rmtree(gate_dir, ignore_errors=True)

                passed = vis_ok and held_ok
                exit_code = 0 if passed else 1
                cur.execute(
                    f"INSERT INTO {art}.TEST_RESULTS "
                    "(task_id, iteration, tool, exit_code, passed, output) "
                    "VALUES (%s,%s,%s,%s,%s,%s)",
                    (task, it, "pytest", exit_code, passed,
                     (vis_out[:4000] + f"\n[held-out: {'PASS' if held_ok else 'FAIL'}]")))
                print(f"[iter {it}] visible={'ok' if vis_ok else 'fail'} "
                      f"heldout={'ok' if held_ok else 'fail'} -> exit={exit_code}",
                      flush=True)

                if passed:
                    cur.execute(f"INSERT INTO {art}.RUNS (task_id, iteration, status, "
                                "detail) VALUES (%s,%s,%s,%s)",
                                (task, it, "DONE", f"passed at iteration {it}"))
                    status = "DONE"
                    print(f"RESULT: DONE at iteration {it}", flush=True)
                    break
                # VISIBLE-only feedback for the next round (anti-bias: current only)
                last_output = vis_out[:5000]
                if vis_ok and not held_ok:
                    last_output += ("\n\nNote: hidden acceptance tests still failing. "
                                    "Re-examine the specification and edge cases.")
            else:
                cur.execute(f"INSERT INTO {art}.RUNS (task_id, iteration, status, "
                            "detail) VALUES (%s,%s,%s,%s)",
                            (task, a.max_iter - 1, "NEEDS_HUMAN",
                             f"no PASS after {a.max_iter} iterations"))
                status = "NEEDS_HUMAN"
                print(f"RESULT: NEEDS_HUMAN after {a.max_iter} iterations", flush=True)

            cur.execute(f"ALTER COMPUTE POOL {pool} SUSPEND")
        print(f"\nFINAL: {status}")
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
