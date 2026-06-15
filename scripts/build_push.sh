#!/usr/bin/env bash
# Build the orchestrator image for a given tag and push to the SPCS registry.
# Usage: build_push.sh <tag>   (assumes `podman login` to the registry already done)
set -euo pipefail

TAG="${1:?usage: build_push.sh <tag>}"
HOST=adesso-aws-de.registry.snowflakecomputing.com
IMG="$HOST/prepsmart/orchestrator/images/orchestrator_base:$TAG"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

podman build --platform linux/amd64 -t "$IMG" -f "$ROOT/docker/Dockerfile" "$ROOT"
podman push "$IMG"
echo "PUSHED: $IMG"
