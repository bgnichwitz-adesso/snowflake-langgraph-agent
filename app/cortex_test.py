"""Package 3 — prove Cortex is reachable from inside the SPCS container using
the internal OAuth token (no External Access Integration).

Reads the session token SPCS mounts at /snowflake/session/token, connects over
the internal SNOWFLAKE_HOST, and calls SNOWFLAKE.CORTEX.COMPLETE. Prints the
response between markers so the job logs can be verified as evidence.
"""
import os
import sys

import snowflake.connector

MODEL = os.environ.get("CORTEX_MODEL", "claude-sonnet-4-6")
PROMPT = "say: HELLO"
TOKEN_PATH = "/snowflake/session/token"


def main() -> int:
    try:
        with open(TOKEN_PATH) as fh:
            token = fh.read()
        conn = snowflake.connector.connect(
            host=os.environ["SNOWFLAKE_HOST"],
            account=os.environ["SNOWFLAKE_ACCOUNT"],
            token=token,
            authenticator="oauth",
            warehouse=os.environ.get("SNOWFLAKE_WAREHOUSE", "DEFAULT_WH"),
        )
        cur = conn.cursor()
        cur.execute(
            "SELECT SNOWFLAKE.CORTEX.COMPLETE(%s, %s)", (MODEL, PROMPT)
        )
        resp = cur.fetchone()[0]
    except Exception as exc:  # noqa: BLE001
        print(f"CORTEX_FAIL: {type(exc).__name__}: {exc}", flush=True)
        return 1

    print("CORTEX_RESPONSE_BEGIN", flush=True)
    print(resp, flush=True)
    print("CORTEX_RESPONSE_END", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
