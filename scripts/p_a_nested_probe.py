"""Form A validation — can a running SPCS container (the orchestrator, as ORCH_PROJ)
launch a CHILD job service (as ORCH_DEV), block on it, and read its result?

This is the one unproven mechanic of Form A (in-container LangGraph loop whose nodes
launch ORCH_DEV/ORCH_TEST jobs via nested EXECUTE JOB SERVICE). If it works, Form A is
viable; if not, we keep the loop in-container but adapt the launch mechanism.

Flow: laptop launches a PARENT job owned by ORCH_PROJ (RUNNER->PROJ). The parent, from
inside the container, connects with its SPCS token, USE ROLE ORCH_DEV, EXECUTE JOB
SERVICE a CHILD (owned by ORCH_DEV) that prints CURRENT_ROLE and writes a marker to the
exchange stage; the parent then reads the child's log + lists the marker. One cheap job
pair. Prereq (set here): GRANT ROLE ORCH_DEV_DEMO TO ROLE ORCH_PROJ_DEMO (downward-safe).
"""
import base64
import sys

import config
from sf import connect

PROJECT = "DEMO"
POOL = config.POOL
IMG = config.spec_image_path("latest")
XSTAGE = config.exchange_stage(PROJECT)          # ORCHESTRATOR.DEMO_XCHG.AGENT_STAGE
PROJ = config.project_role(PROJECT)              # ORCH_PROJ_DEMO
DEV = config.dev_role(PROJECT)                   # ORCH_DEV_DEMO
RUNNER = config.RUNNER_ROLE
CHILD_JOB = f"{config.exchange_schema(PROJECT)}.NEST_CHILD"
PARENT_JOB = f"{config.artifact_schema(PROJECT)}.NEST_PARENT"

# CHILD: connect via its own SPCS token (= ORCH_DEV), prove role + write marker to stage
_CHILD = (
    "import os, snowflake.connector\n"
    "t=open('/snowflake/session/token').read().strip()\n"
    "c=snowflake.connector.connect(host=os.environ['SNOWFLAKE_HOST'],"
    "account=os.environ['SNOWFLAKE_ACCOUNT'],token=t,authenticator='oauth',"
    "warehouse=os.environ.get('SNOWFLAKE_WAREHOUSE','DEFAULT_WH'))\n"
    "r=c.cursor().execute('select current_role()').fetchone()[0]\n"
    "os.makedirs('/xchg/nested',exist_ok=True)\n"
    "open('/xchg/nested/marker.txt','w').write('CHILD_RAN_AS='+r)\n"
    "print('CHILD_DONE role='+r, flush=True)\n"
)
_CHILD_B64 = base64.b64encode(_CHILD.encode()).decode()

CHILD_SPEC = f"""spec:
  containers:
    - name: main
      image: {IMG}
      command: ["python","-u","-c","import base64;exec(base64.b64decode('{_CHILD_B64}'))"]
      env:
        SNOWFLAKE_WAREHOUSE: "{config.WAREHOUSE}"
      volumeMounts:
        - name: xchg
          mountPath: /xchg
  volumes:
    - name: xchg
      source: "@{XSTAGE}"
"""

# PARENT: runs in-container as ORCH_PROJ; launches the child nested + reads its result.
# Reads the child spec from the mounted exchange stage (no spec embedding).
_PARENT = (
    "import os, snowflake.connector\n"
    "t=open('/snowflake/session/token').read().strip()\n"
    "c=snowflake.connector.connect(host=os.environ['SNOWFLAKE_HOST'],"
    "account=os.environ['SNOWFLAKE_ACCOUNT'],token=t,authenticator='oauth',"
    "warehouse=os.environ.get('SNOWFLAKE_WAREHOUSE','DEFAULT_WH'))\n"
    "cur=c.cursor()\n"
    "print('PARENT_ROLE='+cur.execute('select current_role()').fetchone()[0],flush=True)\n"
    "spec=open('/xchg/nested/child_spec.yaml').read()\n"
    f"cur.execute('use role {DEV}')\n"
    f"cur.execute('drop service if exists {CHILD_JOB}')\n"
    "try:\n"
    f"    cur.execute(\"execute job service in compute pool {POOL} name={CHILD_JOB} from specification $$\"+spec+\"$$\")\n"
    "    print('CHILD_LAUNCHED_OK',flush=True)\n"
    "except Exception as e:\n"
    "    print('CHILD_LAUNCH_ERR '+type(e).__name__+': '+str(e)[:250],flush=True)\n"
    "try:\n"
    f"    lg=cur.execute(\"select system$get_service_logs('{CHILD_JOB}','0','main',50)\").fetchone()[0]\n"
    "    print('CHILD_LOG:'+(lg or '')[-250:],flush=True)\n"
    "except Exception as e: print('childlog_err '+str(e)[:150],flush=True)\n"
    f"cur.execute('list @{XSTAGE}/nested')\n"
    "print('MARKER_FILES='+str([x[0] for x in cur.fetchall()]),flush=True)\n"
    f"cur.execute('drop service if exists {CHILD_JOB}')\n"
    "print('PARENT_DONE',flush=True)\n"
)
_PARENT_B64 = base64.b64encode(_PARENT.encode()).decode()

PARENT_SPEC = f"""
spec:
  containers:
    - name: main
      image: {IMG}
      command: ["python","-u","-c","import base64;exec(base64.b64decode('{_PARENT_B64}'))"]
      env:
        SNOWFLAKE_WAREHOUSE: "{config.WAREHOUSE}"
      volumeMounts:
        - name: xchg
          mountPath: /xchg
  volumes:
    - name: xchg
      source: "@{XSTAGE}"
"""


def main() -> int:
    import os
    import tempfile
    try:
        with connect() as conn:
            cur = conn.cursor()
            # Form A prereq: parent (ORCH_PROJ) must be able to assume ORCH_DEV to own
            # the child (downward-safe; ORCH_DEV still can't assume ORCH_PROJ).
            cur.execute(f"GRANT ROLE {DEV} TO ROLE {PROJ}")
            cur.execute("SELECT CURRENT_USER()")
            user = cur.fetchone()[0]
            cur.execute(f"GRANT ROLE {RUNNER} TO USER {user}")

            # stage the child spec + clear old marker
            d = tempfile.mkdtemp(prefix="nest_")
            with open(os.path.join(d, "child_spec.yaml"), "w") as fh:
                fh.write(CHILD_SPEC)
            cur.execute(f"REMOVE @{XSTAGE}/nested")
            cur.execute(f"PUT 'file://{d}/child_spec.yaml' @{XSTAGE}/nested/ "
                        "AUTO_COMPRESS=FALSE OVERWRITE=TRUE")

            # launch PARENT as ORCH_PROJ (RUNNER -> PROJ), synchronous
            cur.execute(f"DROP SERVICE IF EXISTS {PARENT_JOB}")
            cur.execute(f"USE ROLE {RUNNER}")
            cur.execute(f"USE ROLE {PROJ}")
            print("=== EXECUTE PARENT JOB as ORCH_PROJ (launches child nested) ===")
            try:
                cur.execute(f"EXECUTE JOB SERVICE IN COMPUTE POOL {POOL} "
                            f"NAME = {PARENT_JOB} FROM SPECIFICATION $${PARENT_SPEC}$$")
            except Exception as exc:  # noqa: BLE001
                print(f"  parent raised: {type(exc).__name__}: {str(exc)[:200]}")
            cur.execute("USE ROLE ACCOUNTADMIN")
            cur.execute(f"SELECT SYSTEM$GET_SERVICE_LOGS('{PARENT_JOB}', '0', 'main', 500)")
            logs = cur.fetchone()[0] or ""
            print("\n=== PARENT LOGS ===\n" + logs)

            # cleanup
            cur.execute(f"DROP SERVICE IF EXISTS {PARENT_JOB}")
            cur.execute(f"DROP SERVICE IF EXISTS {CHILD_JOB}")
            cur.execute(f"REMOVE @{XSTAGE}/nested")
            cur.execute(f"ALTER COMPUTE POOL {POOL} SUSPEND")

        launched = "CHILD_LAUNCHED_OK" in logs
        child_dev = "CHILD_RAN_AS=ORCH_DEV_DEMO" in logs or "role=ORCH_DEV_DEMO" in logs
        marker = "marker.txt" in logs
        parent_proj = "PARENT_ROLE=ORCH_PROJ_DEMO" in logs
        print("\n=== NESTED-LAUNCH PROBE RESULTS ===")
        print(f"  parent ran as ORCH_PROJ        : {parent_proj}")
        print(f"  nested child launched + blocked : {launched}")
        print(f"  child ran as ORCH_DEV          : {child_dev}")
        print(f"  child wrote marker to exchange : {marker}")
        ok = parent_proj and launched and child_dev and marker
        print(f"\n{'PASS — Form A nested launch works (container launches child job)' if ok else 'FAIL — nested launch not viable as-is'}")
        return 0 if ok else 1
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
