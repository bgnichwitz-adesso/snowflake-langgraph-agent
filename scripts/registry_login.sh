#!/usr/bin/env bash
# Log the container engine in to the SPCS image registry using the PAT.
# Derives the registry host from the live image repository and the username
# from the connections.toml profile — nothing hardcoded.
#
# Prereq: image repository exists (run p2_infra.py first) and .secrets/pat is set.
# Env:    CONTAINER_ENGINE=podman|docker (default: podman, falls back to docker)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="$ROOT/.venv/bin/python"
ENGINE="${CONTAINER_ENGINE:-}"
if [[ -z "$ENGINE" ]]; then
  if command -v podman >/dev/null 2>&1; then ENGINE=podman; else ENGINE=docker; fi
fi

HOST="$("$PY" "$ROOT/scripts/image_uri.py" login | cut -d/ -f1)"
USER_NAME="$(PYTHONPATH="$ROOT/scripts" "$PY" -c \
  "import sf, config; print(sf._conn_params(config.CONNECTION)['user'])")"

echo "Logging in to $HOST as $USER_NAME (engine: $ENGINE) ..."
"$ENGINE" login "$HOST" -u "$USER_NAME" --password-stdin < "$ROOT/.secrets/pat"
