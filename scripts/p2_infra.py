"""Package 2 (part 1) — create SPCS infrastructure objects.

Creates the database, schema, a minimal compute pool, and an image repository
(all names from config / .env). Prints the image repository URL (needed for the
image push) and the compute pool state as evidence. Scope: infra only.
"""
import sys

import config
from sf import connect

DB = config.DATABASE
SCHEMA = config.SCHEMA
POOL = config.POOL
REPO = config.IMAGE_REPO

STATEMENTS = [
    f"CREATE DATABASE IF NOT EXISTS {DB}",
    f"CREATE SCHEMA IF NOT EXISTS {DB}.{SCHEMA}",
    (
        f"CREATE COMPUTE POOL IF NOT EXISTS {POOL} "
        f"MIN_NODES = 1 MAX_NODES = 1 INSTANCE_FAMILY = {config.INSTANCE_FAMILY} "
        "AUTO_SUSPEND_SECS = 600 AUTO_RESUME = TRUE"
    ),
    f"CREATE IMAGE REPOSITORY IF NOT EXISTS {DB}.{SCHEMA}.{REPO}",
]


def main() -> int:
    try:
        with connect() as conn:
            cur = conn.cursor()
            for stmt in STATEMENTS:
                cur.execute(stmt)
                print(f"OK: {stmt[:70]}")

            print("\n=== IMAGE REPOSITORY ===")
            cur.execute(f"SHOW IMAGE REPOSITORIES IN SCHEMA {DB}.{SCHEMA}")
            cols = [c[0].lower() for c in cur.description]
            for row in cur.fetchall():
                rec = dict(zip(cols, row))
                print(f"  name           : {rec.get('name')}")
                print(f"  repository_url : {rec.get('repository_url')}")

            print("\n=== COMPUTE POOL ===")
            cur.execute(f"SHOW COMPUTE POOLS LIKE '{POOL}'")
            cols = [c[0].lower() for c in cur.description]
            for row in cur.fetchall():
                rec = dict(zip(cols, row))
                print(f"  name  : {rec.get('name')}")
                print(f"  state : {rec.get('state')}")
                print(f"  family: {rec.get('instance_family')}")
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
