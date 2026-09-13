# Developer-Agent SQL role — `ORCH_DEV_<ID>` (M6/B)

Canonical grant + Separation-of-Duties reference for the per-project **developer**
agent SQL identity. Designed with Cortex Code (COCO) on 2026-09-13, implemented in
`scripts/register_project.py` (grants) + `scripts/setup_agent_identity.py` (PAT).

## Role model (Separation of Duties)
| Role | Duty | held-out | project DB | can create roles |
|---|---|---|---|---|
| `ORCH_PROJ_<ID>` | orchestrator + **gate** (runs the loop, executes tests) | **read** (gate) | – | no |
| `ORCH_DEV_<ID>` | **developer** agent — builds the Snowflake app | **never** | read-write (broad) | **yes** (app roles) |
| `ORCH_TEST_<ID>` | **tester** agent — writes tests incl. held-out (**1.8**) | **write** | read | (1.8) |

The developer runs SQL as `ORCH_DEV_<ID>` via a role-restricted PAT (SPCS secret,
mounted as `AGENT_PAT`); the container/gate keeps the SPCS OAuth token = `ORCH_PROJ_<ID>`.

## What the developer role CAN do (maximal build capability, project-scoped)
- `USAGE` on the project DB/schema + warehouse; `CORTEX_USER`.
- `CREATE` for every app object type in the project schema: TABLE, VIEW, MATERIALIZED
  VIEW, SEQUENCE, STAGE, FILE FORMAT, FUNCTION, PROCEDURE (Snowpark Python), STREAM,
  TASK, DYNAMIC TABLE, PIPE, STREAMLIT, NOTEBOOK.
- Full DML on tables (`SELECT/INSERT/UPDATE/DELETE/TRUNCATE/REFERENCES`); USAGE on
  functions/procedures/file formats/sequences; OPERATE+MONITOR on tasks/dynamic
  tables/pipes; SELECT on views/materialized views/streams; READ/WRITE on stages.
- **FUTURE** grants for all of the above **WITH GRANT OPTION** → the dev can delegate
  its project privileges to app roles it creates.
- `EXECUTE TASK` + `EXECUTE MANAGED TASK` on account (tasks/serverless run).
- `CREATE ROLE` on account — every app needs its own roles; this is part of the job.

## Two hard guardrails (why escalation is impossible)
1. **No self-escalation.** The dev has **no `MANAGE GRANTS`** and Snowflake enforces
   "you can only grant a privilege you hold (owned or WITH GRANT OPTION)". It has zero
   grants on the `ORCHESTRATOR` control DB → it cannot read held-out and cannot grant
   held-out to anything. `ACCOUNTADMIN` owns the `ORCH_DEV_<ID>` role, so the dev
   cannot alter its own grants.
2. **No acquiring the tester/gate role.** `ORCH_DEV_<ID>` is a **leaf**: granted only
   *to* `ORCH_RUNNER` (assume-down) and `ORCH_AGENT` (its PAT user); no role is granted
   *to* it. It cannot assume `ORCH_TEST_<ID>` or `ORCH_PROJ_<ID>`.

`CREATE ROLE` + `WITH GRANT OPTION` is **not** an escalation path: created roles start
empty and can only receive privileges the dev already holds; ownership of a created
role lets the dev push privileges *down*, never pull them *up*.

## Anti-squatting (residual vector 1 — handled)
With `CREATE ROLE`, the dev could pre-create `ORCH_TEST_<ID>`/`ORCH_PROJ_<ID>` and own
them. `register_project.py` therefore **creates both (incl. an empty reserved
`ORCH_TEST_<ID>` placeholder) BEFORE granting `CREATE ROLE`**, plus the existing
foreign-collision guard. Owning an empty same-named role would gain nothing anyway.

## Deliberately omitted
- **No read access to `ORCHESTRATOR`** (COCO "Step 9" skipped): the developer gets the
  spec and the (visible) test results **only via the orchestrator's prompt**, never by
  SQL. This is intentional **anti-bias** — the agent must not browse the results/test
  history (fresh agent per iteration, current-session feedback only), and it keeps
  held-out fully out of reach.

## Known, deprioritized residual (per decision "nicht beachten", 2026-09-13)
- **`EXECUTE AS CALLER` procedures.** A dev-authored procedure with `EXECUTE AS CALLER`
  runs with the *caller's* rights; if the gate (`ORCH_PROJ`, has held-out) ever executes
  it (e.g. a test calling an app proc), held-out could be exfiltrated. Procedures default
  to `EXECUTE AS OWNER` (= `ORCH_DEV`, no held-out). The robust fix (a dedicated gate
  identity that never executes dev code) is deferred; **not addressed now by decision.**

## Verified (2026-09-13, DEMO)
- Grant DDL applied with **0 failures** (all `CREATE *` incl. NOTEBOOK/STREAMLIT/DYNAMIC
  TABLE/PIPE supported on this edition).
- `SHOW GRANTS TO ROLE ORCH_DEV_DEMO`: **no** grant referencing `ORCHESTRATOR`; **no**
  `MANAGE GRANTS`; **no** role granted *to* it.
- `SHOW GRANTS OF ROLE ORCH_DEV_DEMO`: granted only to `ORCH_AGENT` + `ORCH_RUNNER`.
- `ORCH_TEST_DEMO` reserved placeholder exists.
