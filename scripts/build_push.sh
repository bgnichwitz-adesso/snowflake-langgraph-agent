#!/usr/bin/env bash
# Build the orchestrator image for a given tag and push to the SPCS registry.
# The image URI (incl. registry host) is derived from the live image repository
# via image_uri.py — nothing account-specific is hardcoded.
#
# Prereqs: image repository exists (run p2_infra.py first) and you are logged in
# to the registry (see README — registry login).
#
# Usage: build_push.sh <tag>
# Env:   CONTAINER_ENGINE=podman|docker (default: podman, falls back to docker)
set -euo pipefail

TAG="${1:?usage: build_push.sh <tag>}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="$ROOT/.venv/bin/python"
ENGINE="${CONTAINER_ENGINE:-}"
if [[ -z "$ENGINE" ]]; then
  if command -v podman >/dev/null 2>&1; then ENGINE=podman; else ENGINE=docker; fi
fi

IMG="$("$PY" "$ROOT/scripts/image_uri.py" "$TAG")"
echo "Image URI: $IMG  (engine: $ENGINE)"

"$ENGINE" build --platform linux/amd64 -t "$IMG" -f "$ROOT/docker/Dockerfile" "$ROOT"
"$ENGINE" push "$IMG"
echo "PUSHED: $IMG"
