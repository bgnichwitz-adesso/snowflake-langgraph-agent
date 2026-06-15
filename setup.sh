#!/usr/bin/env bash
# One-time local setup: create the venv and install laptop dependencies.
# Does NOT create any Snowflake objects — see README for the run order.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

if [[ ! -d .venv ]]; then
  echo "Creating .venv ..."
  python3 -m venv .venv
fi
. .venv/bin/activate
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt
echo "venv ready: $(python --version)"

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "Created .env from .env.example — edit it for your account."
else
  echo ".env already present."
fi

echo
echo "Next steps (see README.md):"
echo "  1. Edit .env (SF_CONNECTION, SF_WAREHOUSE, ...)."
echo "  2. Ensure ~/.snowflake/connections.toml has your SF_CONNECTION profile."
echo "  3. Put a PAT in .secrets/pat (or let the first run use browser auth)."
echo "  4. Run the bootstrap packages per the README."
