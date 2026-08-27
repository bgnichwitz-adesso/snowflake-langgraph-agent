"""Shared Cortex Code agent auth bootstrap (in-container).

The agent CLI authenticates with the SPCS internal OAuth token via a
connections.toml (env token alone is not enough — the CLI resolves the agent
connection from connections.toml). Single internal identity — NO PAT. Also sets
offline-safe env (no auto-update / telemetry) so the CLI only touches the
account host.

Call bootstrap_agent_auth() before running the SDK; returns (CONN_NAME, AGENT_ENV).
"""
import os

SF_HOME = "/tmp/sfhome"
CONN_NAME = "spcs"
TOKEN_PATH = next((p for p in ("/snowflake/session/token",
                               "/snowflake/session/spcs_token")
                   if os.path.exists(p)), None)

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


def _write_connections_toml() -> None:
    os.makedirs(SF_HOME, exist_ok=True)
    lines = [f'default_connection_name = "{CONN_NAME}"', "",
             f"[{CONN_NAME}]",
             f'account = "{os.environ.get("SNOWFLAKE_ACCOUNT", "")}"',
             f'host = "{os.environ.get("SNOWFLAKE_HOST", "")}"',
             'authenticator = "oauth"',
             f'token_file_path = "{TOKEN_PATH}"']
    wh = os.environ.get("SNOWFLAKE_WAREHOUSE", "")
    if wh:
        lines.append(f'warehouse = "{wh}"')
    path = os.path.join(SF_HOME, "connections.toml")
    with open(path, "w") as fh:
        fh.write("\n".join(lines) + "\n")
    os.chmod(path, 0o600)


def bootstrap_agent_auth():
    """Idempotent: export the token, set agent env, write connections.toml.

    Returns (CONN_NAME, AGENT_ENV) for CortexCodeAgentOptions(connection=..., env=...).
    """
    if not TOKEN_PATH:
        raise RuntimeError("no SPCS session token (/snowflake/session/token)")
    os.environ["SNOWFLAKE_TOKEN"] = open(TOKEN_PATH).read().strip()
    os.environ.update(AGENT_ENV)
    _write_connections_toml()
    return CONN_NAME, AGENT_ENV
