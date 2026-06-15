"""Package 6 — roles, append-only TASK_SPECS table, grants, and current view.

Creates the 5 PREPSMART_* roles, an append-only TASK_SPECS table (carrying
tenant_id + user_id + status), grants INSERT only to PREPSMART_LEAD and SELECT
to the others, and the TASK_SPECS_CURRENT view. Asserts the three pass
conditions and prints evidence.
"""
import sys

import config
from sf import connect

DB = config.DATABASE
SCHEMA = config.SCHEMA
FQT = f"{DB}.{SCHEMA}.TASK_SPECS"
FQV = f"{DB}.{SCHEMA}.TASK_SPECS_CURRENT"

ROLES = [
    "PREPSMART_LEAD",
    "PREPSMART_DEVELOPER",
    "PREPSMART_TESTER",
    "PREPSMART_ORCHESTRATOR",
    "PREPSMART_HUMAN_IN_LOOP",
]
SELECT_ROLES = ROLES[1:]  # everyone except LEAD

DDL = [
    *[f"CREATE ROLE IF NOT EXISTS {r}" for r in ROLES],
    f"""CREATE TABLE IF NOT EXISTS {FQT} (
        task_id     STRING        NOT NULL,
        tenant_id   STRING        NOT NULL DEFAULT 'DEFAULT',
        user_id     STRING        NOT NULL,
        status      STRING        NOT NULL DEFAULT 'DRAFT',
        title       STRING,
        spec_text   STRING,
        created_at  TIMESTAMP_NTZ NOT NULL DEFAULT CURRENT_TIMESTAMP(),
        created_by  STRING        NOT NULL DEFAULT CURRENT_USER()
    )""",
    # Append-only: enforced structurally by granting LEAD only INSERT
    # (no UPDATE/DELETE grant ever). History = new rows.
    f"""CREATE OR REPLACE VIEW {FQV} AS
        SELECT * FROM {FQT}
        QUALIFY ROW_NUMBER() OVER (
            PARTITION BY task_id ORDER BY created_at DESC) = 1""",
]

# Usage so roles can reach the objects; LEAD = INSERT only, others = SELECT.
GRANTS = []
for r in ROLES:
    GRANTS.append(f"GRANT USAGE ON DATABASE {DB} TO ROLE {r}")
    GRANTS.append(f"GRANT USAGE ON SCHEMA {DB}.{SCHEMA} TO ROLE {r}")
GRANTS.append(f"GRANT INSERT ON TABLE {FQT} TO ROLE PREPSMART_LEAD")
for r in SELECT_ROLES:
    GRANTS.append(f"GRANT SELECT ON TABLE {FQT} TO ROLE {r}")
    GRANTS.append(f"GRANT SELECT ON VIEW {FQV} TO ROLE {r}")


def main() -> int:
    try:
        with connect() as conn:
            cur = conn.cursor()
            for stmt in DDL + GRANTS:
                cur.execute(stmt)
            print(f"OK: executed {len(DDL)} DDL + {len(GRANTS)} grant statements")

            # --- Test 1: 5 roles ---
            print("\n=== SHOW ROLES LIKE 'PREPSMART_%' ===")
            cur.execute("SHOW ROLES LIKE 'PREPSMART_%'")
            cols = [c[0].lower() for c in cur.description]
            found = []
            for row in cur.fetchall():
                rec = dict(zip(cols, row))
                found.append(rec["name"])
                print(f"  {rec['name']}")
            t1 = sorted(found) == sorted(ROLES)
            print(f"  -> {len(found)} roles, expected 5: {'PASS' if t1 else 'FAIL'}")

            # --- Test 2: INSERT only for LEAD ---
            print(f"\n=== SHOW GRANTS ON TABLE {FQT} ===")
            cur.execute(f"SHOW GRANTS ON TABLE {FQT}")
            cols = [c[0].lower() for c in cur.description]
            insert_grantees, select_grantees = [], []
            for row in cur.fetchall():
                rec = dict(zip(cols, row))
                priv, grantee = rec.get("privilege"), rec.get("grantee_name")
                print(f"  {priv:10} -> {grantee}")
                if priv == "INSERT":
                    insert_grantees.append(grantee)
                if priv == "SELECT":
                    select_grantees.append(grantee)
            t2 = insert_grantees == ["PREPSMART_LEAD"] and sorted(
                select_grantees
            ) == sorted(SELECT_ROLES)
            print(
                f"  -> INSERT grantees={insert_grantees}; "
                f"SELECT grantees={sorted(select_grantees)}: "
                f"{'PASS' if t2 else 'FAIL'}"
            )

            # --- Test 3: view runs ---
            print(f"\n=== SELECT * FROM {FQV} ===")
            cur.execute(f"SELECT COUNT(*) FROM {FQV}")
            n = cur.fetchone()[0]
            print(f"  view query OK, row count = {n}")
            t3 = True

        ok = t1 and t2 and t3
        print(f"\n{'PASS — all 3 conditions green' if ok else 'FAIL'}")
        return 0 if ok else 1
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
