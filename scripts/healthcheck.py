"""End-to-end health check for the orchestrator deployment.

One config-driven script (nothing to adapt per account) that verifies the whole
stack and reports OK / NOT OK per check plus an overall result. Exit code 0 if
all checks pass, 1 otherwise.

Checks (all names come from .env / config):
  1. connection      — SELECT CURRENT_VERSION()
  2. infra           — database, schema, compute pool, image repository exist
  3. image           — base image present in the repository
  4. control_plane   — 5 ORCH_* roles; TASK_SPECS (INSERT only for LEAD),
                        PROJECTS, and TASK_SPECS_CURRENT exist
  5. container_e2e   — a job-service runs the LangGraph flow inside the
                        container (covers SPCS, internal OAuth, Cortex, langgraph)

Leaves the compute pool suspended (zero cost) and drops its own test job.

Usage: python scripts/healthcheck.py [image_tag]   (default tag: latest)
"""
import sys

import config
from sf import connect

DB, SCHEMA, POOL = config.DATABASE, config.SCHEMA, config.POOL
JOB = f"{DB}.{SCHEMA}.HEALTHCHECK_JOB"


def _rows(cur, sql):
    cur.execute(sql)
    cols = [c[0].lower() for c in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def check_connection(cur) -> str:
    cur.execute("SELECT CURRENT_VERSION(), CURRENT_ACCOUNT_NAME(), CURRENT_ROLE()")
    v, acct, role = cur.fetchone()
    return f"version {v}, account {acct}, role {role}"


def check_infra(cur) -> str:
    assert _rows(cur, f"SHOW DATABASES LIKE '{DB}'"), f"database {DB} missing"
    assert _rows(cur, f"SHOW SCHEMAS LIKE '{SCHEMA}' IN DATABASE {DB}"), \
        f"schema {DB}.{SCHEMA} missing"
    pools = _rows(cur, f"SHOW COMPUTE POOLS LIKE '{POOL}'")
    assert pools, f"compute pool {POOL} missing"
    repos = _rows(cur, f"SHOW IMAGE REPOSITORIES LIKE '{config.IMAGE_REPO}' "
                       f"IN SCHEMA {DB}.{SCHEMA}")
    assert repos, f"image repository {config.IMAGE_REPO} missing"
    return f"db+schema ok, pool {POOL} ({pools[0]['state']}), repo ok"


def check_image(cur) -> str:
    imgs = _rows(cur, f"SHOW IMAGES IN IMAGE REPOSITORY {DB}.{SCHEMA}.{config.IMAGE_REPO}")
    names = [i.get("image_name") for i in imgs]
    assert any(config.IMAGE_NAME in (n or "") for n in names), \
        f"image {config.IMAGE_NAME} not found in repo (have: {names})"
    return f"image {config.IMAGE_NAME} present"


def check_control_plane(cur) -> str:
    roles = sorted(r["name"] for r in _rows(cur, f"SHOW ROLES LIKE '{config.ROLE_PREFIX}_%'"))
    assert sorted(config.ROLES) == roles, f"roles mismatch: {roles}"
    grants = _rows(cur, f"SHOW GRANTS ON TABLE {DB}.{SCHEMA}.TASK_SPECS")
    inserts = [g["grantee_name"] for g in grants if g.get("privilege") == "INSERT"]
    assert inserts == [config.LEAD_ROLE], f"INSERT grantees != [{config.LEAD_ROLE}]: {inserts}"
    tables = {t["name"] for t in _rows(cur, f"SHOW TABLES IN SCHEMA {DB}.{SCHEMA}")}
    assert {"TASK_SPECS", "PROJECTS"} <= tables, f"tables missing: {tables}"
    views = {v["name"] for v in _rows(cur, f"SHOW VIEWS IN SCHEMA {DB}.{SCHEMA}")}
    assert "TASK_SPECS_CURRENT" in views, "view TASK_SPECS_CURRENT missing"
    return f"{len(roles)} roles, INSERT→{config.LEAD_ROLE}, TASK_SPECS+PROJECTS+view ok"


def check_container_e2e(cur, tag: str) -> str:
    spec = f"""
spec:
  containers:
    - name: main
      image: {config.spec_image_path(tag)}
      command: ["python", "-u", "/app/langgraph_flow.py"]
      env:
        CORTEX_MODEL: "{config.CORTEX_MODEL}"
        SNOWFLAKE_WAREHOUSE: "{config.WAREHOUSE}"
"""
    cur.execute(f"DROP SERVICE IF EXISTS {JOB}")
    try:
        cur.execute(f"EXECUTE JOB SERVICE IN COMPUTE POOL {POOL} NAME = {JOB} "
                    f"FROM SPECIFICATION $${spec}$$")
    except Exception as exc:  # noqa: BLE001 - inspect logs regardless
        raise AssertionError(f"job failed: {str(exc)[:160]}") from None
    cur.execute(f"SELECT SYSTEM$GET_SERVICE_LOGS('{JOB}', '0', 'main', 1000)")
    logs = cur.fetchone()[0] or ""
    assert "SYSTEM OK" in logs, f"flow output missing 'SYSTEM OK'; logs: {logs[:200]}"
    return "container ran flow → Cortex → 'SYSTEM OK'"


CHECKS = [
    ("connection", check_connection),
    ("infra", check_infra),
    ("image", check_image),
    ("control_plane", check_control_plane),
    ("container_e2e", check_container_e2e),
]


def main() -> int:
    tag = sys.argv[1] if len(sys.argv) > 1 else "latest"
    results = []
    try:
        with connect() as conn:
            cur = conn.cursor()
            for name, fn in CHECKS:
                try:
                    detail = fn(cur, tag) if name == "container_e2e" else fn(cur)
                    results.append((name, True, detail))
                    print(f"[  OK   ] {name:14} — {detail}")
                except Exception as exc:  # noqa: BLE001
                    results.append((name, False, f"{type(exc).__name__}: {exc}"))
                    print(f"[ NOT OK] {name:14} — {type(exc).__name__}: {exc}")
            # always clean up
            try:
                cur.execute(f"DROP SERVICE IF EXISTS {JOB}")
                cur.execute(f"ALTER COMPUTE POOL {POOL} SUSPEND")
            except Exception as exc:  # noqa: BLE001
                print(f"(cleanup warning: {exc})")
    except Exception as exc:  # noqa: BLE001
        print(f"[ NOT OK] connection     — {type(exc).__name__}: {exc}")
        print("\nRESULT: NOT OK (could not connect)")
        return 1

    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    ok = passed == total
    print("\n" + ("RESULT: OK" if ok else "RESULT: NOT OK")
          + f" ({passed}/{total} checks passed)")
    if not ok:
        for name, good, detail in results:
            if not good:
                print(f"  FAILED {name}: {detail}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
