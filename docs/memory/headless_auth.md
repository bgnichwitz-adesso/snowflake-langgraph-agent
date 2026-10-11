---
name: headless-auth
description: "How laptop-side scripts authenticate to Snowflake headlessly — PAT in .secrets/pat, not EXTERNALBROWSER"
metadata: 
  node_type: memory
  type: project
  originSessionId: 2b145440-804c-4c3d-b27f-df03d873100a
---

Laptop-side Phase 0 scripts authenticate to Snowflake with a **Programmatic Access Token (PAT)**, stored at `.secrets/pat` (gitignored, chmod 600) in the repo. `scripts/sf.py:connect()` reads it and connects with `authenticator="PROGRAMMATIC_ACCESS_TOKEN"`, pulling account/user/role/warehouse from `~/.snowflake/connections.toml` profile `ADESSO_AWS_DE`.

**Why:** The `ADESSO_AWS_DE` connection uses EXTERNALBROWSER auth, which can't open a browser from a non-interactive shell (WSL2) and does NOT cache an SSO id-token unless the account has `ALLOW_ID_TOKEN=TRUE`. Enabling that param did not produce a working headless cache in testing, so we switched to a PAT (headless by design, no account-wide toggle).

**How to apply:** Run any laptop SQL via the venv: `.venv/bin/python scripts/<script>.py`. It's headless. If auth fails, the PAT likely expired — user mints a new one (Snowsight → user → Programmatic access tokens) and overwrites `.secrets/pat`. Connection verified working: role ACCOUNTADMIN, account AWS_DE, warehouse DEFAULT_WH. See [[phase0-tasks]].
