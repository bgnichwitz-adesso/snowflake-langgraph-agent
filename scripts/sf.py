"""Shared Snowflake connection helper for laptop-side scripts.

Auth strategy:
  - If a PAT exists at config.PAT_FILE, connect headlessly with it.
  - Otherwise fall back to the connection's authenticator from connections.toml
    (e.g. EXTERNALBROWSER — interactive, used once to mint the PAT).

All names come from config (driven by .env). Nothing account-specific here.
"""
import tomllib
from pathlib import Path

import snowflake.connector

import config

CONNECTIONS_TOML = Path.home() / ".snowflake" / "connections.toml"


def _conn_params(connection_name: str) -> dict:
    with open(CONNECTIONS_TOML, "rb") as fh:
        cfg = tomllib.load(fh)
    if connection_name not in cfg:
        avail = [k for k in cfg if isinstance(cfg[k], dict)]
        raise KeyError(
            f"connection '{connection_name}' not in {CONNECTIONS_TOML}. "
            f"Available: {avail}"
        )
    return cfg[connection_name]


def _load_pat() -> str | None:
    if config.PAT_FILE.exists():
        tok = config.PAT_FILE.read_text().strip()
        return tok or None
    return None


def connect_browser(connection_name: str | None = None):
    """Interactive connection per connections.toml (used once to mint a PAT)."""
    return snowflake.connector.connect(
        connection_name=connection_name or config.CONNECTION
    )


def connect(connection_name: str | None = None):
    """Headless if a PAT is cached, else interactive browser auth."""
    name = connection_name or config.CONNECTION
    pat = _load_pat()
    if not pat:
        return connect_browser(name)

    p = _conn_params(name)
    return snowflake.connector.connect(
        account=p["account"],
        user=p["user"],
        authenticator="PROGRAMMATIC_ACCESS_TOKEN",
        token=pat,
        role=p.get("role"),
        warehouse=p.get("warehouse", config.WAREHOUSE),
    )
