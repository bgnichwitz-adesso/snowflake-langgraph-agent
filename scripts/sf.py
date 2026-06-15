"""Shared Snowflake connection helper for Phase 0 laptop-side scripts.

Auth strategy:
  - If a cached PAT exists (.secrets/pat), connect headlessly with it.
  - Otherwise fall back to the EXTERNALBROWSER connection from
    connections.toml (interactive — used once to mint the PAT).
"""
import os
import tomllib
from pathlib import Path

import snowflake.connector

DEFAULT_CONNECTION = "ADESSO_AWS_DE"
PAT_FILE = Path(__file__).resolve().parent.parent / ".secrets" / "pat"
CONNECTIONS_TOML = Path.home() / ".snowflake" / "connections.toml"


def _conn_params(connection_name: str = DEFAULT_CONNECTION) -> dict:
    with open(CONNECTIONS_TOML, "rb") as fh:
        cfg = tomllib.load(fh)
    return cfg[connection_name]


def _load_pat() -> str | None:
    if PAT_FILE.exists():
        tok = PAT_FILE.read_text().strip()
        return tok or None
    return None


def connect_browser(connection_name: str = DEFAULT_CONNECTION):
    """Interactive EXTERNALBROWSER connection (used once to mint the PAT)."""
    return snowflake.connector.connect(connection_name=connection_name)


def connect(connection_name: str = DEFAULT_CONNECTION):
    """Headless if a PAT is cached, else interactive browser auth."""
    pat = _load_pat()
    if not pat:
        return connect_browser(connection_name)

    p = _conn_params(connection_name)
    return snowflake.connector.connect(
        account=p["account"],
        user=p["user"],
        authenticator="PROGRAMMATIC_ACCESS_TOKEN",
        token=pat,
        role=p.get("role"),
        warehouse=p.get("warehouse"),
    )
