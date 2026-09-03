"""Shared Cortex Code agent auth bootstrap (in-container).

Two identities, one container (M6/B):
  - the Python orchestrator + gate connect with the SPCS internal OAuth token =
    the service-owner role ORCH_PROJ_<ID> (has held-out). That is NOT set up here.
  - the AGENT (this module) authenticates as a LEAST-PRIV identity so its SQL tool
    cannot read the orchestrator artifact schema (held-out). If AGENT_PAT is present
    (an SPCS secret for the ORCH_APP_<ID> role), the agent connection uses that PAT;
    otherwise it falls back to the SPCS OAuth token (single-identity, no SQL isolation).

Call bootstrap_agent_auth() before running the SDK; returns (CONN_NAME, AGENT_ENV).
"""
import os

SF_HOME = "/tmp/sfhome"
TOKEN_PATH = next((p for p in ("/snowflake/session/token",
                               "/snowflake/session/spcs_token")
                   if os.path.exists(p)), None)

_PAT = os.environ.get("AGENT_PAT", "").strip()
CONN_NAME = "app" if _PAT else "spcs"

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


def _common(lines: list) -> None:
    acct = os.environ.get("SNOWFLAKE_ACCOUNT", "")
    host = os.environ.get("SNOWFLAKE_HOST", "")
    lines += [f'account = "{acct}"', f'host = "{host}"']
    wh = os.environ.get("SNOWFLAKE_WAREHOUSE", "")
    if wh:
        lines.append(f'warehouse = "{wh}"')


def _write_connections_toml() -> None:
    os.makedirs(SF_HOME, exist_ok=True)
    lines = [f'default_connection_name = "{CONN_NAME}"', "", f"[{CONN_NAME}]"]
    _common(lines)
    if _PAT:
        # Least-priv agent identity (ORCH_APP_<ID>) via programmatic access token.
        user = os.environ.get("AGENT_USER", "")
        role = os.environ.get("AGENT_ROLE", "")
        lines += [f'user = "{user}"',
                  'authenticator = "programmatic_access_token"',
                  f'token = "{_PAT}"']
        if role:
            lines.append(f'role = "{role}"')
    else:
        # Fallback: single internal identity via the SPCS OAuth token.
        lines += ['authenticator = "oauth"',
                  f'token_file_path = "{TOKEN_PATH}"']
    path = os.path.join(SF_HOME, "connections.toml")
    with open(path, "w") as fh:
        fh.write("\n".join(lines) + "\n")
    os.chmod(path, 0o600)


def bootstrap_agent_auth():
    """Idempotent: set agent env + write connections.toml for the agent identity.

    Returns (CONN_NAME, AGENT_ENV) for CortexCodeAgentOptions(connection=..., env=...).
    """
    if not _PAT and not TOKEN_PATH:
        raise RuntimeError("no agent credential: neither AGENT_PAT nor SPCS token")
    if not _PAT:
        os.environ["SNOWFLAKE_TOKEN"] = open(TOKEN_PATH).read().strip()
    os.environ.update(AGENT_ENV)
    _write_connections_toml()
    return CONN_NAME, AGENT_ENV
