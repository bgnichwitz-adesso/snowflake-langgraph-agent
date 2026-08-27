"""M2 — prove the Cortex Code agent actually RUNS inside the SPCS container.

Single internal identity (no PAT): the CLI reads the SPCS OAuth token. We set the
token as SNOWFLAKE_TOKEN and force the agent's inference to reuse the SQL
connection; auto-update + telemetry are disabled so nothing but the account host
is contacted. The agent is asked to create a trivial file; success = a
ResultMessage without error AND a file produced in the cwd.

Prints stable markers: AGENT_HELLO_OK / AGENT_HELLO_FAIL: <reason>.
"""
import asyncio
import os
import sys

CWD = "/tmp/agent_hello"
SF_HOME = "/tmp/sfhome"
CONN_NAME = "spcs"
TOKEN_PATH = next((p for p in ("/snowflake/session/token",
                               "/snowflake/session/spcs_token")
                   if os.path.exists(p)), None)

# --- internal auth: a named oauth connection backed by the SPCS token file.
# The CLI resolves the agent connection from connections.toml (env token alone
# isn't enough — the CLI errors "No Snowflake connection available"). ---
if TOKEN_PATH:
    os.environ["SNOWFLAKE_TOKEN"] = open(TOKEN_PATH).read().strip()


def _write_connections_toml() -> None:
    os.makedirs(SF_HOME, exist_ok=True)
    account = os.environ.get("SNOWFLAKE_ACCOUNT", "")
    host = os.environ.get("SNOWFLAKE_HOST", "")
    wh = os.environ.get("SNOWFLAKE_WAREHOUSE", "")
    lines = [f'default_connection_name = "{CONN_NAME}"', "",
             f"[{CONN_NAME}]",
             f'account = "{account}"',
             f'host = "{host}"',
             'authenticator = "oauth"',
             f'token_file_path = "{TOKEN_PATH}"']
    if wh:
        lines.append(f'warehouse = "{wh}"')
    path = os.path.join(SF_HOME, "connections.toml")
    with open(path, "w") as fh:
        fh.write("\n".join(lines) + "\n")
    os.chmod(path, 0o600)


# --- offline-safe + SPCS + single-identity env (also passed via options.env) ---
AGENT_ENV = {
    "SNOWFLAKE_HOME": SF_HOME,
    "SNOWFLAKE_DEFAULT_CONNECTION_NAME": CONN_NAME,
    "SNOWFLAKE_RUNNING_INSIDE_SPCS": "true",
    "COCO_CLI_CONNECTION_OVERRIDES_INFERENCE": "1",
    "COCO_TELEMETRY_DISABLED": "true",
    "COCO_DATADOG_DISABLED": "true",
    "COCO_OTEL_DISABLED": "true",
    "CORTEX_CODE_AGENT_SDK_SKIP_VERSION_CHECK": "1",
    "SF_SKIP_TOKEN_FILE_PERMISSIONS_VERIFICATION": "true",
}
os.environ.update(AGENT_ENV)
if TOKEN_PATH:
    _write_connections_toml()


async def run() -> int:
    from cortex_code_agent_sdk import CortexCodeAgentOptions, query

    os.makedirs(CWD, exist_ok=True)
    opts_kwargs = dict(
        cwd=CWD,
        connection=CONN_NAME,
        permission_mode="bypassPermissions",
        allow_dangerously_skip_permissions=True,
        max_turns=3,
        env=AGENT_ENV,
        extra_args={"no-auto-update": None},
    )
    model = os.environ.get("CORTEX_MODEL")
    if model:
        opts_kwargs["model"] = model
    options = CortexCodeAgentOptions(**opts_kwargs)

    result = None
    async for message in query(
        prompt="Create a file named hello.txt containing exactly 'hello world', then stop.",
        options=options,
    ):
        kind = type(message).__name__
        if kind == "ResultMessage":
            result = message
            print(f"RESULT: subtype={getattr(message,'subtype',None)} "
                  f"is_error={getattr(message,'is_error',None)}", flush=True)

    files = sorted(os.listdir(CWD))
    print(f"cwd files: {files}", flush=True)
    is_error = getattr(result, "is_error", True) if result is not None else True
    if result is not None and not is_error and files:
        print("AGENT_HELLO_OK", flush=True)
        return 0
    print(f"AGENT_HELLO_FAIL: result={result is not None} is_error={is_error} "
          f"files={files}", flush=True)
    return 1


def main() -> int:
    if not os.environ.get("SNOWFLAKE_TOKEN"):
        print("AGENT_HELLO_FAIL: no SPCS session token found", flush=True)
        return 1
    try:
        return asyncio.run(run())
    except Exception as exc:  # noqa: BLE001
        print(f"AGENT_HELLO_FAIL: {type(exc).__name__}: {exc}", flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
