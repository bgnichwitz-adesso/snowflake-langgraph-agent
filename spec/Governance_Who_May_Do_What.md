# Governance — Who May Do What (authoritative)

Status: **✏️ decided 2026-06-30.** This is the single source of truth for actor
permissions across the orchestrator. Other specs reference it; if they disagree,
this file wins.

## Principle
Agents build and test. **Humans own the blast radius.** Anything that changes the
account's security posture, network reach, privilege graph, or destroys objects is
**done by a human (HUMAN_IN_LOOP) before the run** and is **forbidden to every
orchestrator agent** — including the SPEC Judge.

## Actors
| Actor | Kind | Role/identity |
|---|---|---|
| **LEAD** | Human | authors + locks `TASK_SPECS` (INSERT only) |
| **HUMAN_IN_LOOP (HITL)** | Human | provisions account prerequisites + the forbidden class; approves the account-change manifest; runs deploy/grant scripts with elevated rights |
| **SPEC Judge** | Agent (Phase 2) | read-only over SPEC + account; extracts infra requirements, flags gaps; **proposes, never provisions** |
| **DEVELOPER** | Agent (Cortex Code SDK) | builds project-scoped artifacts under `ORCH_PROJ_<ID>`; reads provisioned params |
| **TESTER** | Agent | derives frozen tests (incl. held-out) from the acceptance contract → `TEST_SPECS` |
| **RUNNER / orchestrator** | Deterministic code | control flow + gate (exit-code only); writes `RUNS`; no LLM judgment |
| **ORCH_PROJ_\<ID\>** | Snowflake role | the least-priv identity the build/test runs under |

## FORBIDDEN to every agent (HITL-only, provisioned BEFORE the night run)
No orchestrator agent — **not even the Judge** — may do any of these. They are done
by HITL beforehand and verified by the Phase-2 deterministic verifier:

1. **Account parameters** — `ALTER ACCOUNT SET …`.
2. **Security / external integrations** — `EXTERNAL ACCESS INTEGRATION`, `SECURITY
   INTEGRATION`, `API INTEGRATION`, `STORAGE INTEGRATION`.
3. **Network objects** — `NETWORK RULE`, `NETWORK POLICY`.
4. **Privilege management to foreign principals** — `MANAGE GRANTS`, and any
   `GRANT … TO ROLE/USER` outside the project's own owned objects.
5. **Destruction** — `DROP` and `CREATE OR REPLACE` (implicit drop) on anything.

These are exactly the data-exfiltration / blast-radius / privilege-spread surface.

## Permission matrix
| Capability | LEAD | HITL | Judge | DEVELOPER | TESTER | RUNNER |
|---|---|---|---|---|---|---|
| Author/lock TASK_SPECS | ✅ INSERT | — | read | read | read | read (LOCKED) |
| Read SPEC + account (SHOW/DESCRIBE) | ✅ | ✅ | ✅ RO | ✅ (provisioned params only) | ✅ | ✅ |
| Forbidden class (above) | — | ✅ (pre-run) | ❌ | ❌ | ❌ | ❌ |
| Account objects: DB/schema/pool/warehouse/role* | — | ✅ | ❌ | **mode-dependent** (see below) | ❌ | ❌ |
| Project-scoped build (tables/views/procs/streamlit/schema-services) | — | ✅ | ❌ | ✅ under `ORCH_PROJ_<ID>` | ❌ | ❌ |
| Derive + freeze tests (`TEST_SPECS`, held-out) | — | — | ❌ | ❌ | ✅ | read |
| Write code + `DEV_COMMENTS` | — | — | ❌ | ✅ | ❌ | — |
| Decide PASS/FAIL (gate) | — | — | ❌ | ❌ | ❌ | ✅ (exit-code only) |
| Write `RUNS` (outcome) | — | — | ❌ | ❌ | ❌ | ✅ |
| Approve account-change manifest / run deploy scripts | — | ✅ | ❌ | ❌ | ❌ | ❌ |

\* roles **without** `MANAGE GRANTS`; **never** DROP/OR REPLACE.

## Two modes (set at SPEC handover)
- **Restricted** (shared account): HITL pre-provisions **all** account-level objects;
  DEVELOPER has **no** account-create rights — project-scoped only.
- **Isolated** (ideal DEV, account-isolated): DEVELOPER may CREATE the **non-forbidden**
  account objects (DB/schema/pool/warehouse/role) via a **custom role** (broad CREATE
  **minus** the forbidden class, **no DROP/OR REPLACE**). The **forbidden class stays
  HITL-only, pre-provisioned, in both modes.**

In **both** modes every account-level CREATE is recorded as **idempotent DDL in the
deliverable repo** + an append-only **account-change manifest** (Phase 3) — autonomy
never removes the duty to record.

## Custom role (isolated mode)
No built-in role grants "all CREATE except security integrations", so define
`ORCH_BUILDER_<ID>`: grant the account-level CREATE privileges the SPEC needs, **omit**
the forbidden class, **omit** DROP. Worth the effort — it is the only way to bound
autonomous account-level building without exposing the blast-radius surface.
