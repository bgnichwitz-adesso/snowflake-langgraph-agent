"""Cortex Code agent auth bootstrap (in-container).

M6/B: the developer agent runs in its OWN SPCS job owned by ORCH_DEV_<ID>, so the
container's internal SPCS OAuth token already IS the least-priv developer identity
(ORCH_DEV: project-DB build rights + CORTEX, no orchestrator artifact schema). The
agent therefore authenticates with that SPCS token via a runtime connections.toml —
no PAT, no second credential (the PAT path was dropped: the account's network policy
blocks PAT logins from the SPCS egress, while the internal OAuth token is exempt).

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
    """Idempotent: export the SPCS token, set agent env, write connections.toml.

    Returns (CONN_NAME, AGENT_ENV) for CortexCodeAgentOptions(connection=..., env=...).
    """
    if not TOKEN_PATH:
        raise RuntimeError("no SPCS session token (/snowflake/session/token)")
    os.environ["SNOWFLAKE_TOKEN"] = open(TOKEN_PATH).read().strip()
    os.environ.update(AGENT_ENV)
    _write_connections_toml()
    return CONN_NAME, AGENT_ENV
