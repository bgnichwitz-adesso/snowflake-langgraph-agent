"""Package 1 — verify Snowflake connection from the laptop.

Pass condition: SELECT CURRENT_VERSION() returns a version number.
Evidence printed: Snowflake version + account name + role + warehouse.
"""
import sys

from sf import connect


def main() -> int:
    try:
        with connect() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT CURRENT_VERSION(), CURRENT_ACCOUNT_NAME(), "
                "CURRENT_ROLE(), CURRENT_WAREHOUSE()"
            )
            version, account, role, wh = cur.fetchone()
    except Exception as exc:  # noqa: BLE001 - surface full error per global rules
        print(f"FAIL: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    print("PASS — Snowflake connection verified")
    print(f"  CURRENT_VERSION : {version}")
    print(f"  ACCOUNT_NAME    : {account}")
    print(f"  ROLE            : {role}")
    print(f"  WAREHOUSE       : {wh}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
