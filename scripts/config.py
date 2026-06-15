"""Central configuration for the orchestrator bootstrap.

Single source of truth for all account/object names. Values resolve in this
precedence: real environment variable > .env file (repo root) > built-in
default. No third-party dependency — .env is parsed here.

Edit .env (copy from .env.example) to target a different account / database /
warehouse / model. Nothing else needs editing.
"""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = ROOT / ".env"


def _load_env_file() -> None:
    if not ENV_FILE.exists():
        return
    for raw in ENV_FILE.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        # Real env vars take precedence over the file.
        os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))


_load_env_file()


def _get(key: str, default: str) -> str:
    return os.environ.get(key, default)


# --- Snowflake connection / objects ---
CONNECTION = _get("SF_CONNECTION", "ADESSO_AWS_DE")
DATABASE = _get("SF_DATABASE", "PREPSMART")
SCHEMA = _get("SF_SCHEMA", "ORCHESTRATOR")
POOL = _get("SF_POOL", "PREPSMART_POOL_XS")
WAREHOUSE = _get("SF_WAREHOUSE", "DEFAULT_WH")
INSTANCE_FAMILY = _get("SF_INSTANCE_FAMILY", "CPU_X64_XS")

# --- Image repository / image ---
IMAGE_REPO = _get("SF_IMAGE_REPO", "IMAGES")
IMAGE_NAME = _get("SF_IMAGE_NAME", "orchestrator_base")

# --- Cortex ---
CORTEX_MODEL = _get("CORTEX_MODEL", "claude-sonnet-4-6")

# --- Auth ---
PAT_FILE = ROOT / _get("SF_PAT_FILE", ".secrets/pat")


def spec_image_path(tag: str) -> str:
    """Image path as referenced inside an SPCS service spec — relative to the
    registry and lowercased: /<db>/<schema>/<repo>/<image>:<tag>."""
    return f"/{DATABASE}/{SCHEMA}/{IMAGE_REPO}/{IMAGE_NAME}:{tag}".lower()
