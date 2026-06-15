"""Enable account-level SSO id-token caching so the connector can authenticate
headlessly after the first interactive login.

Sets ALLOW_ID_TOKEN = TRUE (requires ACCOUNTADMIN) and prints the resulting
parameter value as evidence.
"""
import sys

from sf import connect


def main() -> int:
    try:
        with connect() as conn:
            cur = conn.cursor()
            cur.execute("ALTER ACCOUNT SET ALLOW_ID_TOKEN = TRUE")
            cur.execute("SHOW PARAMETERS LIKE 'ALLOW_ID_TOKEN' IN ACCOUNT")
            row = cur.fetchone()
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    # SHOW PARAMETERS columns: key, value, default, level, description, type
    print("ALLOW_ID_TOKEN set.")
    print(f"  key   : {row[0]}")
    print(f"  value : {row[1]}")
    print(f"  level : {row[3]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
