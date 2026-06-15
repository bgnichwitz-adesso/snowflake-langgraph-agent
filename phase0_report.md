# Phase 0 — Bootstrap Report

**Date:** 2026-06-15
**Branch:** `phase0-bootstrap`
**Result:** ✅ All 6 packages PASS

Goal of Phase 0: a runnable orchestrator base — a LangGraph flow inside an SPCS
container reaching Claude via Cortex over the internal path. Achieved.

---

## Environment as built

| Item | Value |
|---|---|
| Snowflake account | `AWS_DE` (org `ADESSO-AWS_DE`), region eu-central-1 |
| Connection profile | `ADESSO_AWS_DE` (role `ACCOUNTADMIN`, wh `DEFAULT_WH`) |
| Laptop auth | **PAT** at `.secrets/pat` (gitignored) — see note 1 |
| Database / schema | `PREPSMART` / `ORCHESTRATOR` |
| Compute pool | `PREPSMART_POOL_XS` (CPU_X64_XS, 1 node, auto-suspend 600s) |
| Image repository | `adesso-aws-de.registry.snowflakecomputing.com/prepsmart/orchestrator/images` |
| Container build | podman 4.9.3, rootless, `--platform linux/amd64` |
| Image | `orchestrator_base` (tags: phase0, p3, p4, p5) |
| Python (container) | 3.11-slim · snowflake-connector-python 4.6.0 · langgraph 1.2.5 |

---

## Package status + evidence

### Package 1 — Snowflake connection — ✅ PASS
`scripts/p1_connect.py`
```
CURRENT_VERSION : 10.20.102
ACCOUNT_NAME    : AWS_DE
ROLE            : ACCOUNTADMIN
WAREHOUSE       : DEFAULT_WH
```

### Package 2 — SPCS container — ✅ PASS
`scripts/p2_infra.py` + `scripts/p2_service.py`
```
image in repo : orchestrator_base:phase0
service       : PREPSMART.ORCHESTRATOR.BOOTSTRAP_SVC
instance      : READY
SHOW SERVICES : RUNNING
```

### Package 3 — Cortex from container — ✅ PASS
`app/cortex_test.py` run as job service; internal OAuth token, no EAI.
```
CORTEX_RESPONSE_BEGIN
**HELLO** 👋
CORTEX_RESPONSE_END
```

### Package 4 — LangGraph installed — ✅ PASS
`scripts/run_job.py` import check in-container.
```
langgraph 1.2.5
```
Library only (MIT). NOT langgraph-api / langgraph-cli (Elastic License 2.0).

### Package 5 — First LangGraph flow with Cortex — ✅ PASS
`app/langgraph_flow.py` — single node `call_claude` → Cortex.
```
GRAPH_OUTPUT_BEGIN
SYSTEM OK
GRAPH_OUTPUT_END
```

### Package 6 — Roles + grants — ✅ PASS
`scripts/p6_roles.py`
```
roles: PREPSMART_LEAD, _DEVELOPER, _TESTER, _ORCHESTRATOR, _HUMAN_IN_LOOP (5)
TASK_SPECS grants: INSERT -> [PREPSMART_LEAD] only; SELECT -> other 4
TASK_SPECS_CURRENT view: query OK (0 rows)
```

---

## Notes / deliberate decisions

1. **PAT instead of EXTERNALBROWSER caching.** The `ADESSO_AWS_DE` profile uses
   EXTERNALBROWSER, which can't open a browser from a non-interactive shell and
   does not cache an SSO id-token unless `ALLOW_ID_TOKEN=TRUE`. Enabling that
   param did not yield a working headless cache in testing, so we use a
   Programmatic Access Token (role-scoped, headless, no account-wide toggle).
   The same PAT authenticates the podman registry login.

2. **Cortex via SQL `COMPLETE`, not the snowpark `Complete(...)` wrapper.**
   The arch note shows `snowflake.cortex.Complete(model, prompt, session=...)`.
   We call `SELECT SNOWFLAKE.CORTEX.COMPLETE(...)` over the connector instead —
   functionally identical (internal, no egress) and avoids pulling snowpark /
   pandas / pyarrow into the image. **Confirm this is acceptable**, or Phase 1
   switches to the snowpark wrapper.

3. **Bootstrap service is long-running (sleep), not a job-service.** Package 2's
   gate is status READY, which a run-to-completion job never shows. The
   real orchestrator runs as a **job-service** (Packages 3–5 already use
   `EXECUTE JOB SERVICE`). The persistent `BOOTSTRAP_SVC` exists only to prove
   READY and can be dropped.

---

## Open points for Phase 1

- [ ] Drop or repurpose `BOOTSTRAP_SVC` (it holds the compute pool warm).
- [ ] Decide Cortex call style: SQL `COMPLETE` vs snowpark wrapper (note 2).
- [ ] PAT lifecycle: expiry/rotation; move off ACCOUNTADMIN to a least-priv role.
- [ ] Remaining tables (DEV_COMMENTS, TEST_RESULTS, TENANTS, USERS, …) + Row
      Access Policies for multi-tenant isolation (TENANT_ID + USER_ID).
- [ ] Orchestrator loop: load_task → claude_generate → run_tests → gate →
      commit/next | feed-back/retry (MAX iterations → STOP), LangGraph
      checkpointing on a mounted stage.
- [ ] Wire roles to actual users; grant the orchestrator SELECT on LOCKED specs.
- [ ] CI: pin image deps (requirements.txt with hashes), tag images by build.

---

## How to re-run (headless)

```bash
. .venv/bin/activate
python scripts/p1_connect.py        # Package 1
python scripts/p2_infra.py          # Package 2 infra
python scripts/p2_service.py        # Package 2 service -> READY
bash   scripts/build_push.sh p3     # rebuild/push (tags p3..p5)
python scripts/p3_cortex.py         # Package 3
python scripts/run_job.py --tag p4 --name LANGGRAPH_CHECK_JOB --expect "langgraph " -- python -u -c "import langgraph, importlib.metadata as m; print('langgraph', m.version('langgraph'))"
python scripts/run_job.py --tag p5 --name LANGGRAPH_FLOW_JOB  --expect "SYSTEM OK" -- python -u /app/langgraph_flow.py
python scripts/p6_roles.py          # Package 6
```
