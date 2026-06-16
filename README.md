# Snowflake LangGraph Orchestrator — Bootstrap

Sets up a deterministic LangGraph orchestrator that runs inside a **Snowpark
Container Services (SPCS)** container and calls Claude via **Cortex** over the
internal OAuth path (no External Access Integration). This repo currently
contains the **Phase 0 bootstrap** — the 6 steps that stand up the base
infrastructure. See `phase0_report.md` for the architecture rationale and
`spec/` for the full specification.

Every account-specific value lives in **`.env`** — set it once and the scripts
target your account, database, warehouse, and model. No code edits needed.

> **Status:** Phase 0 (bootstrap) is **complete** — see `phase0_report.md` for
> evidence and `docs/SESSION_PROTOCOL_2026-06-15.md` for the full session record
> and where to continue (Phase 1). On the original account the Snowflake objects
> already exist; the run order below is for a **fresh account / colleague setup**.

---

## Prerequisites

- **Python 3.11+** (for the local `.venv`).
- **podman** or **docker** (rootless podman is fine; set `CONTAINER_ENGINE` to
  pick one). Needs network to Docker Hub to pull `python:3.11-slim`.
- A **Snowflake account** and a role that can `CREATE COMPUTE POOL`,
  `CREATE ROLE`, and create image repositories/services (e.g. `ACCOUNTADMIN`).
- The account's region must offer the **Cortex model** you set in `CORTEX_MODEL`.
- A connection profile in **`~/.snowflake/connections.toml`** (see below).

---

## One-time setup

```bash
./setup.sh                 # creates .venv, installs deps, seeds .env
```

Then:

### 1. Configure your connection (`~/.snowflake/connections.toml`)
```toml
[MY_CONNECTION]
account       = "MYORG-MYACCOUNT"
user          = "ME@EXAMPLE.COM"
authenticator = "EXTERNALBROWSER"     # or your auth method
warehouse     = "MY_WAREHOUSE"
role          = "ACCOUNTADMIN"
```
`chmod 600 ~/.snowflake/connections.toml` (the connector enforces this).

### 2. Edit `.env`
Set at least `SF_CONNECTION` (the profile name above) and `SF_WAREHOUSE`.
Defaults exist for the rest — see `.env.example`.

### 3. Provide a Programmatic Access Token (PAT)
Scripts authenticate headlessly with a PAT (browser SSO can't run from a
non-interactive shell and won't cache without `ALLOW_ID_TOKEN`). Mint one in
**Snowsight → your user → Programmatic access tokens** (role-restricted, with an
expiry), then:
```bash
mkdir -p .secrets && chmod 700 .secrets
printf '%s' '<YOUR_PAT>' > .secrets/pat && chmod 600 .secrets/pat
```
`.secrets/` is gitignored. (Without a PAT, the first run falls back to the
connections.toml authenticator — interactive.)

---

## Bootstrap run order

All commands assume the venv is active: `. .venv/bin/activate`.

```bash
# 1 — verify the Snowflake connection
python scripts/p1_connect.py

# 2 — create infra (db, schema, compute pool, image repository)
python scripts/p2_infra.py
bash   scripts/registry_login.sh          # log engine in to the registry
bash   scripts/build_push.sh phase0        # build + push the base image
python scripts/p2_service.py phase0        # create service, wait for READY

# 3 — Cortex reachable from inside the container
bash   scripts/build_push.sh p3
python scripts/p3_cortex.py p3

# 4 — langgraph present in the image
python scripts/run_job.py --tag p3 --name LANGGRAPH_CHECK_JOB \
  --expect "langgraph " -- \
  python -u -c "import langgraph, importlib.metadata as m; print('langgraph', m.version('langgraph'))"

# 5 — minimal LangGraph flow calling Cortex
python scripts/run_job.py --tag p3 --name LANGGRAPH_FLOW_JOB \
  --expect "SYSTEM OK" -- python -u /app/langgraph_flow.py

# 6 — roles, append-only TASK_SPECS, grants, current view
python scripts/p6_roles.py
```

Each script prints **PASS** with evidence (version, status, query result) or
**FAIL** with the full error. Stop on any FAIL.

> The image is rebuilt per tag only to keep package boundaries clean; once set
> up you can use a single tag (e.g. `latest`) for everything from step 3 on.

---

## Register a project

The orchestrator is multi-project. Each project (whose database the project team
already owns) is onboarded once — no code change:

```bash
python scripts/register_project.py --id DEMO --project-db DEMO_PROJ \
    --description "what this project is"
```
This creates the per-project execution role `ORCH_PROJ_<ID>` (tagged), the
artifact schema `ORCHESTRATOR.<ID>` (with `CODE_STAGE`, `DEV_COMMENTS`,
`TEST_RESULTS`), grants the role on the existing project DB + artifacts, grants
it to `ORCH_RUNNER`, and writes a row to `ORCHESTRATOR.CORE.PROJECTS`. Tasks in
`TASK_SPECS` reference their `project_id`; the loop looks it up and runs under
the project's execution role. A name collision with a *foreign* account-level
role is raised as an exception (not silently reused).

---

## Health check

One config-driven script verifies the whole deployment and prints **OK / NOT OK**
per check plus an overall result (exit 0 = all good). Nothing to adapt per
account; run it anytime to confirm the stack is healthy.

```bash
python scripts/healthcheck.py        # checks connection, infra, image,
                                     # control-plane, and a container e2e run
```
It runs a job-service end-to-end (SPCS → internal OAuth → Cortex → LangGraph
flow), then **drops its test job and suspends the compute pool** — so it never
leaves anything running that would block auto-suspend.

---

## Cleanup (stop billing)

The compute pool bills while a **service** runs. Job-services exit on their own
and let the pool auto-suspend. To stop everything immediately:

```bash
python - <<'PY'
import sys; sys.path.insert(0, "scripts")
import config
from sf import connect
with connect() as c:
    cur = c.cursor()
    cur.execute(f"DROP SERVICE IF EXISTS {config.DATABASE}.{config.SCHEMA}.BOOTSTRAP_SVC")
    cur.execute(f"ALTER COMPUTE POOL {config.POOL} SUSPEND")
    print("service dropped, pool suspended")
PY
```
The pool has `AUTO_RESUME = TRUE`, so the next job-service restarts it.

---

## Troubleshooting

- **Connection hangs / opens a browser repeatedly** — you have no PAT and are on
  EXTERNALBROWSER. Add a PAT to `.secrets/pat` (see setup step 3).
- **`connection '...' not in connections.toml`** — `SF_CONNECTION` in `.env`
  doesn't match a profile name in `~/.snowflake/connections.toml`.
- **Registry login fails** — run `python scripts/p2_infra.py` first (the image
  repository must exist), and confirm the PAT is valid/not expired.
- **Cortex error: model not available** — `CORTEX_MODEL` isn't offered in your
  account's region; pick a model your region supports.

---

## Repo layout

| Path | What |
|---|---|
| `scripts/config.py` | central config (reads `.env`) |
| `scripts/sf.py` | Snowflake connection helper (PAT → headless) |
| `scripts/p*.py` | per-package bootstrap steps |
| `scripts/run_job.py` | generic SPCS job-service runner |
| `scripts/build_push.sh`, `registry_login.sh`, `image_uri.py` | image pipeline |
| `app/` | code that runs **inside** the container |
| `docker/` | Dockerfile + pinned image deps |
| `spec/` | full project specification |

Contributing / git workflow: see `CONTRIBUTING.md`.
