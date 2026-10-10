"""M6/B validation — does an ORCH_DEV-owned SPCS service's token bypass the
network policy (like the gate token does), so the developer can run SQL WITHOUT a PAT?

Launches a minimal job service OWNED BY ORCH_DEV_<ID> (chain RUNNER -> ORCH_DEV) that
connects with its OWN SPCS OAuth token and runs SQL against the project DB. If it
connects (no "IP not allowed" error) and returns CURRENT_ROLE=ORCH_DEV_<ID>, the
"second identity = its own SPCS service" approach is confirmed — no PAT needed.

Grants ORCH_DEV the minimal service-execution rights first (pool/image-repo/CREATE
SERVICE); these stay for the real nested-generate() design. Cheap: one tiny job.
"""
import base64
import sys

import config
from sf import connect

DB, SCHEMA, POOL = config.DATABASE, config.SCHEMA, config.POOL
PROJECT = "DEMO"
DEV = config.dev_role(PROJECT)                 # ORCH_DEV_DEMO
RUNNER = config.RUNNER_ROLE
PROJ_DB, PROJ_SCHEMA = "DEMO_PROJ", "PUBLIC"
JOB = f"{PROJ_DB}.{PROJ_SCHEMA}.DEVTOKEN_PROBE"

# In-container: connect via the SPCS token (oauth) and prove SQL as ORCH_DEV.
_CODE = (
    "import os, snowflake.connector\n"
    "t=open('/snowflake/session/token').read().strip()\n"
    "c=snowflake.connector.connect(host=os.environ['SNOWFLAKE_HOST'],"
    "account=os.environ['SNOWFLAKE_ACCOUNT'],token=t,authenticator='oauth',"
    "warehouse=os.environ.get('SNOWFLAKE_WAREHOUSE','DEFAULT_WH'))\n"
    "cur=c.cursor()\n"
    "cur.execute('select current_user(), current_role()'); print('WHOAMI', cur.fetchone(), flush=True)\n"
    "cur.execute('select count(*) from DEMO_PROJ.PUBLIC.SAMPLE_DATA'); print('PROJ_SQL_OK', cur.fetchone(), flush=True)\n"
    "print('DEVTOKEN_PROBE_DONE', flush=True)\n"
)
_B64 = base64.b64encode(_CODE.encode()).decode()


def main() -> int:
    tag = sys.argv[1] if len(sys.argv) > 1 else "latest"
    spec = f"""
spec:
  containers:
    - name: main
      image: {config.spec_image_path(tag)}
      command: ["python", "-u", "-c", "import base64;exec(base64.b64decode('{_B64}'))"]
      env:
        SNOWFLAKE_WAREHOUSE: "{config.WAREHOUSE}"
"""
    try:
        with connect() as conn:
            cur = conn.cursor()
            print("=== grant ORCH_DEV minimal service-execution rights ===")
            grants = [
                f"GRANT USAGE ON COMPUTE POOL {POOL} TO ROLE {DEV}",
                f"GRANT USAGE ON DATABASE {DB} TO ROLE {DEV}",
                f"GRANT USAGE ON SCHEMA {DB}.{SCHEMA} TO ROLE {DEV}",
                f"GRANT READ ON IMAGE REPOSITORY {DB}.{SCHEMA}.{config.IMAGE_REPO} TO ROLE {DEV}",
                f"GRANT CREATE SERVICE ON SCHEMA {PROJ_DB}.{PROJ_SCHEMA} TO ROLE {DEV}",
            ]
            for g in grants:
                cur.execute(g)
            print("  granted (pool, ORCHESTRATOR.CORE usage, image READ, CREATE SERVICE)")

            cur.execute("SELECT CURRENT_USER()")
            user = cur.fetchone()[0]
            cur.execute(f"GRANT ROLE {RUNNER} TO USER {user}")   # idempotent
            cur.execute(f"DROP SERVICE IF EXISTS {JOB}")

            # launch chain: RUNNER -> ORCH_DEV -> EXECUTE (owner = ORCH_DEV)
            cur.execute(f"USE ROLE {RUNNER}")
            cur.execute(f"USE ROLE {DEV}")
            print(f"\n=== EXECUTE JOB SERVICE as {DEV} ===")
            try:
                cur.execute(f"EXECUTE JOB SERVICE IN COMPUTE POOL {POOL} NAME = {JOB} "
                            f"FROM SPECIFICATION $${spec}$$")
                print("  job finished")
            except Exception as exc:  # noqa: BLE001
                print(f"  job raised: {type(exc).__name__}: {str(exc)[:200]}")

            cur.execute("USE ROLE ACCOUNTADMIN")
            cur.execute(f"SELECT SYSTEM$GET_SERVICE_LOGS('{JOB}', '0', 'main', 1000)")
            logs = cur.fetchone()[0] or ""
            print("\n=== CONTAINER LOGS ===")
            print(logs)
            cur.execute(f"DROP SERVICE IF EXISTS {JOB}")
            cur.execute(f"ALTER COMPUTE POOL {POOL} SUSPEND")

        ip_blocked = "is not allowed to access Snowflake" in logs
        connected = "WHOAMI" in logs and "ORCH_DEV_DEMO" in logs
        sql_ok = "PROJ_SQL_OK" in logs
        print("\n=== DEV-TOKEN PROBE RESULTS ===")
        print(f"  connected as ORCH_DEV via SPCS token : {connected}")
        print(f"  project-DB SQL worked               : {sql_ok}")
        print(f"  network-policy IP block             : {ip_blocked}")
        ok = connected and sql_ok and not ip_blocked
        print(f"\n{'PASS — ORCH_DEV SPCS token bypasses the policy; no PAT needed' if ok else 'FAIL'}")
        return 0 if ok else 1
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
