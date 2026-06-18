"""Cortex generation client (runs inside the SPCS container).

Wraps SNOWFLAKE.CORTEX.COMPLETE in its 3-arg JSON form: a messages array
(system/user/assistant turns) + an options object. Returns the generated text
AND the token usage — the basis for deterministic generation (temperature=0) and
per-task cost tracking.

Reaches Cortex over the internal OAuth token (no External Access Integration).
"""
import json
import os

import snowflake.connector

DEFAULT_MODEL = os.environ.get("CORTEX_MODEL", "claude-sonnet-4-6")
TOKEN_PATH = "/snowflake/session/token"


def _connect():
    with open(TOKEN_PATH) as fh:
        token = fh.read()
    return snowflake.connector.connect(
        host=os.environ["SNOWFLAKE_HOST"],
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        token=token,
        authenticator="oauth",
        warehouse=os.environ.get("SNOWFLAKE_WAREHOUSE", "DEFAULT_WH"),
    )


def cortex_complete(
    messages,
    model: str = None,
    temperature: float = 0,
    max_tokens: int = 4096,
    conn=None,
) -> dict:
    """Call Cortex COMPLETE with messages + options; return text + usage.

    messages: list of {"role": "system|user|assistant", "content": str}
    Returns: {"text": str, "usage": dict, "model": str, "raw": dict}
    """
    model = model or DEFAULT_MODEL
    options = {"temperature": temperature, "max_tokens": max_tokens}
    own_conn = conn is None
    conn = conn or _connect()
    try:
        cur = conn.cursor()
        # PARSE_JSON binds keep the array/object well-formed and injection-safe.
        cur.execute(
            "SELECT SNOWFLAKE.CORTEX.COMPLETE(%s, PARSE_JSON(%s), PARSE_JSON(%s))",
            (model, json.dumps(messages), json.dumps(options)),
        )
        raw = json.loads(cur.fetchone()[0])
    finally:
        if own_conn:
            conn.close()

    # 3-arg JSON shape: {"choices":[{"messages": "..."}], "usage": {...}, ...}
    text = raw.get("choices", [{}])[0].get("messages", "")
    return {
        "text": text,
        "usage": raw.get("usage", {}),
        "model": raw.get("model", model),
        "raw": raw,
    }


if __name__ == "__main__":
    # Self-test: prove text + token usage come back. Printed between markers so
    # the job log can be asserted as evidence.
    import sys

    msgs = [
        {"role": "system", "content": "You are a terse assistant."},
        {"role": "user", "content": "Reply with exactly: GEN OK"},
    ]
    try:
        result = cortex_complete(msgs, temperature=0, max_tokens=20)
    except Exception as exc:  # noqa: BLE001
        print(f"CORTEX_FAIL: {type(exc).__name__}: {exc}", flush=True)
        sys.exit(1)

    u = result["usage"]
    print("CORTEX_GEN_BEGIN", flush=True)
    print(f"text={result['text']!r}", flush=True)
    print(f"model={result['model']}", flush=True)
    print(
        f"usage prompt={u.get('prompt_tokens')} "
        f"completion={u.get('completion_tokens')} "
        f"total={u.get('total_tokens')}",
        flush=True,
    )
    print("CORTEX_GEN_END", flush=True)
    ok = bool(result["text"]) and u.get("total_tokens") is not None
    sys.exit(0 if ok else 1)
