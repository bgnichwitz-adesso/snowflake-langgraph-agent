"""Paket 1.1 — register a project with the orchestrator.

For a project whose database already exists (the project team owns it), this:
  - creates the per-project execution role ORCH_PROJ_<ID> (account-level, tagged),
  - creates the per-project artifact schema ORCHESTRATOR.<ID> with CODE_STAGE,
    DEV_COMMENTS and TEST_RESULTS (append-only),
  - grants the role: USAGE on the existing project DB/schema, and
    INSERT/SELECT on the artifact tables + READ/WRITE on the stage,
  - grants the role to ORCH_RUNNER (so the runner can assume it),
  - records the mapping in ORCHESTRATOR.CORE.PROJECTS.

Safety (per arch decisions):
  - account-level role: collision with a FOREIGN/untagged role raises an
    Exception (no silent reuse); an existing role tagged as ours is reused.
  - only CREATE / CREATE IF NOT EXISTS — never CREATE OR REPLACE (implicit drop).
  - no DROP privileges are granted to any orchestrator role.

Usage:
  register_project.py --id DEMO --project-db DEMO_PROJ \\
      [--project-schema PUBLIC] [--description "..."]
"""
import argparse
import sys

import config
from sf import connect


def _rows(cur, sql):
    cur.execute(sql)
    cols = [c[0].lower() for c in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def assert_role_free_or_ours(cur, role: str) -> None:
    """Collision guard for the account-level role."""
    existing = _rows(cur, f"SHOW ROLES LIKE '{role}'")
    if not existing:
        return
    comment = (existing[0].get("comment") or "")
    if config.MANAGED_BY not in comment:
        raise RuntimeError(
            f"EXCEPTION: role {role} already exists and is NOT managed by this "
            f"orchestrator instance (comment={comment!r}). Account-level name "
            f"collision — needs user intervention; not reusing silently."
        )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", required=True, help="project id, e.g. DEMO")
    ap.add_argument("--project-db", required=True, help="existing project database")
    ap.add_argument("--project-schema", default="PUBLIC")
    ap.add_argument("--description", default="")
    a = ap.parse_args()

    pid = a.id.upper()
    role = config.project_role(pid)
    art = config.artifact_schema(pid)              # ORCHESTRATOR.<ID>
    stage = f"{art}.CODE_STAGE"
    proj_db, proj_schema = a.project_db, a.project_schema
    projects = f"{config.DATABASE}.{config.SCHEMA}.PROJECTS"

    try:
        with connect() as conn:
            cur = conn.cursor()

            # 0) sanity: the project database must already exist
            if not _rows(cur, f"SHOW DATABASES LIKE '{proj_db}'"):
                raise RuntimeError(
                    f"project database {proj_db} does not exist — the project "
                    f"owns it and must be created first (orchestrator is a guest)."
                )

            # 1) execution role (collision-guarded, tagged)
            assert_role_free_or_ours(cur, role)
            cur.execute(
                f"CREATE ROLE IF NOT EXISTS {role} COMMENT = '{config.MANAGED_BY}'"
            )

            # 2) artifact schema + stage + append-only tables (DB-scoped, isolated)
            ddl = [
                f"CREATE SCHEMA IF NOT EXISTS {art}",
                f"CREATE STAGE IF NOT EXISTS {stage}",
                f"""CREATE TABLE IF NOT EXISTS {art}.DEV_COMMENTS (
                    task_id    STRING NOT NULL,
                    iteration  INTEGER NOT NULL DEFAULT 0,
                    author     STRING,
                    comment    STRING,
                    created_at TIMESTAMP_NTZ NOT NULL DEFAULT CURRENT_TIMESTAMP(),
                    created_by STRING NOT NULL DEFAULT CURRENT_USER()
                )""",
                f"""CREATE TABLE IF NOT EXISTS {art}.TEST_RESULTS (
                    task_id    STRING NOT NULL,
                    iteration  INTEGER NOT NULL DEFAULT 0,
                    tool       STRING,
                    exit_code  INTEGER,
                    passed     BOOLEAN,
                    output     STRING,
                    created_at TIMESTAMP_NTZ NOT NULL DEFAULT CURRENT_TIMESTAMP(),
                    created_by STRING NOT NULL DEFAULT CURRENT_USER()
                )""",
                # Orchestrator run outcomes (append-only). TASK_SPECS stays the
                # LEAD-owned immutable input; RUNS is "what happened".
                f"""CREATE TABLE IF NOT EXISTS {art}.RUNS (
                    task_id    STRING NOT NULL,
                    iteration  INTEGER,
                    status     STRING,
                    detail     STRING,
                    created_at TIMESTAMP_NTZ NOT NULL DEFAULT CURRENT_TIMESTAMP(),
                    created_by STRING NOT NULL DEFAULT CURRENT_USER()
                )""",
            ]
            for stmt in ddl:
                cur.execute(stmt)

            # 3) grants for the execution role
            grants = [
                # reach the orchestrator artifact area
                f"GRANT USAGE ON DATABASE {config.DATABASE} TO ROLE {role}",
                f"GRANT USAGE ON SCHEMA {art} TO ROLE {role}",
                f"GRANT READ, WRITE ON STAGE {stage} TO ROLE {role}",
                f"GRANT INSERT, SELECT ON TABLE {art}.DEV_COMMENTS TO ROLE {role}",
                f"GRANT INSERT, SELECT ON TABLE {art}.TEST_RESULTS TO ROLE {role}",
                f"GRANT INSERT, SELECT ON TABLE {art}.RUNS TO ROLE {role}",
                # read the task control-plane (table + current view + registry)
                f"GRANT USAGE ON SCHEMA {config.DATABASE}.{config.SCHEMA} TO ROLE {role}",
                f"GRANT SELECT ON TABLE {config.DATABASE}.{config.SCHEMA}.TASK_SPECS TO ROLE {role}",
                f"GRANT SELECT ON VIEW {config.DATABASE}.{config.SCHEMA}.TASK_SPECS_CURRENT TO ROLE {role}",
                f"GRANT SELECT ON TABLE {config.DATABASE}.{config.SCHEMA}.PROJECTS TO ROLE {role}",
                # service-execution (Paket 1.6b): run the loop job under this role
                f"GRANT USAGE ON WAREHOUSE {config.WAREHOUSE} TO ROLE {role}",
                f"GRANT USAGE ON COMPUTE POOL {config.POOL} TO ROLE {role}",
                f"GRANT READ ON IMAGE REPOSITORY "
                f"{config.DATABASE}.{config.SCHEMA}.{config.IMAGE_REPO} TO ROLE {role}",
                f"GRANT CREATE SERVICE ON SCHEMA {art} TO ROLE {role}",
                # guest access on the existing project DB (baseline; refine per project)
                f"GRANT USAGE ON DATABASE {proj_db} TO ROLE {role}",
                f"GRANT USAGE ON SCHEMA {proj_db}.{proj_schema} TO ROLE {role}",
                f"GRANT SELECT ON ALL TABLES IN SCHEMA {proj_db}.{proj_schema} TO ROLE {role}",
                # allow the role to call Cortex (the loop generates under it)
                f"GRANT DATABASE ROLE SNOWFLAKE.CORTEX_USER TO ROLE {role}",
                # let the runner assume this project role
                f"GRANT ROLE {role} TO ROLE {config.RUNNER_ROLE}",
            ]
            for stmt in grants:
                cur.execute(stmt)

            # 4) registry row (append-only; skip if an identical ACTIVE row exists)
            existing = _rows(
                cur,
                f"SELECT 1 FROM {projects} WHERE project_id = '{pid}' "
                f"AND execution_role = '{role}' AND status = 'ACTIVE' LIMIT 1",
            )
            if not existing:
                cur.execute(
                    f"INSERT INTO {projects} (project_id, description, "
                    "execution_role, project_database, project_schema, "
                    "artifact_schema, code_stage) VALUES "
                    "(%s, %s, %s, %s, %s, %s, %s)",
                    (pid, a.description, role, proj_db, proj_schema, art,
                     f"@{stage}"),
                )
                print(f"  registry row inserted for {pid}")
            else:
                print(f"  registry row for {pid} already present (idempotent)")

            # --- evidence ---
            print(f"\n=== role {role} granted to {config.RUNNER_ROLE}? ===")
            grants_of = _rows(cur, f"SHOW GRANTS OF ROLE {role}")
            to_runner = [g for g in grants_of
                         if g.get("grantee_name") == config.RUNNER_ROLE]
            print(f"  granted to RUNNER: {bool(to_runner)}")

            print(f"\n=== PROJECTS row ===")
            for r in _rows(cur, f"SELECT project_id, execution_role, project_database, "
                                f"artifact_schema, code_stage, status FROM {projects} "
                                f"WHERE project_id = '{pid}'"):
                print(f"  {r}")

            print(f"\n=== artifact schema {art} objects ===")
            tabs = {t["name"] for t in _rows(cur, f"SHOW TABLES IN SCHEMA {art}")}
            stages = {s["name"] for s in _rows(cur, f"SHOW STAGES IN SCHEMA {art}")}
            print(f"  tables: {sorted(tabs)}  stages: {sorted(stages)}")

            ok = (
                bool(to_runner)
                and {"DEV_COMMENTS", "TEST_RESULTS", "RUNS"} <= tabs
                and "CODE_STAGE" in stages
            )
            print(f"\n{'PASS — project ' + pid + ' registered' if ok else 'FAIL'}")
            return 0 if ok else 1
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
