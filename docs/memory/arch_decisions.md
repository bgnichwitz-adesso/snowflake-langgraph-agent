---
name: arch-decisions
description: "Key architecture decisions for the LangGraph orchestrator on SPCS — deterministic gating, Cortex-internal calls, append-only tables, 5 Snowflake roles"
metadata: 
  node_type: memory
  type: project
  originSessionId: 6f1f11b8-8aba-4b15-9aee-e9e196b22c62
  modified: 2026-08-07T18:15:38.050Z
---

## Core principle: Determinism over self-discipline
Claude is a pure code worker. A deterministic orchestrator decides pass/fail via hard test results — not LLM judgment.

**Why:** Claude has historically rationalized away failures. Structural enforcement prevents this.

**How to apply:** Never let Claude declare something "done." Gate always runs pytest/ruff/mypy/dbt-tests. Only green exit code = PASS.

## Orchestrator loop (LangGraph)
```
load_task → claude_generate → run_tests → [pass?]
   ├─ pass → commit → next_task
   └─ fail → feed_test_output_back → claude_generate (loop)
              └─ if iterations ≥ MAX → STOP + report
```

## Hosting: SPCS Job-Service
- Compute Pool + Image Repository in Snowflake
- Job-Service (run-to-completion) for overnight runs
- State/checkpoints on mounted Stages (resumable via LangGraph checkpointing)
- Private Link secures external access; Cortex call is internal (no egress)

## Claude via Cortex (internal, no EAI)
- OAuth token from `/snowflake/session/token` + `SNOWFLAKE_HOST`
- **DECIDED (Phase 0):** call the SQL function `SELECT SNOWFLAKE.CORTEX.COMPLETE(...)` via snowflake-connector-python — NOT the snowpark `snowflake.cortex.Complete(...)` wrapper. Same backend; the SQL path keeps the image light (connector only, no snowpark/pandas/pyarrow) and is a stable contract. **Why:** image weight + API churn outweigh the wrapper's ergonomics for a rebuilt-often worker container.
- **Phase 1 form:** use the 3-arg JSON form — messages array (system+user), options `{'temperature': 0, 'max_tokens': ...}`, and parse the returned JSON for `choices` + `usage` (token counts for cost tracking). temperature=0 for max repeatability (gating is still the hard authority).
- No External Access Integration needed
- Trade-off: bound to Cortex-available models/regions + rate limits (429 → exponential backoff)
- Fallback: native Anthropic API only if latest API-only model is needed → then EAI + Secret. Model used so far: `claude-sonnet-4-6`.

## Worker pivot: agentic worker, not single-shot COMPLETE (decided 2026-06-28, design)
**Supersedes the single-shot `COMPLETE` worker above for code generation.** The one-shot returns a whole solution and *guesses* — over iterations it often degrades, not converges. Replace it with an **agentic worker = Cortex Code Agent SDK** (`cortex-code-agent-sdk`, pip; spawns the `cortex` CLI binary, ~210 MB). It writes/runs/iterates within a task and returns a schema-validated artifact (`output_format`) to the orchestrator, which the **unchanged deterministic gate** tests.
- **Why the SDK, not a hand-rolled ReAct loop:** `COMPLETE`/`AI_COMPLETE` have **no native tool-use** (only temperature/top_p/max_tokens/guardrails/response_format). A hand-rolled ReAct agent would be Snowflake-naive; Cortex Code already knows Snowflake (deploy, Streamlit-in-Snowflake, Snowpark, dbt). Don't reinvent it.
- **Determinism preserved:** worker is agentic/non-deterministic; the frozen-test gate stays the sole "done" authority.
- `cortex_client.py` (COMPLETE) kept as legacy/fallback + possible 1.8 TESTER generation.

## Egress: account endpoint reachable from SPCS WITHOUT an EAI (empirical, 2026-06-28)
Tested: an SPCS container reached `https://<account>.snowflakecomputing.com` (= its injected `SNOWFLAKE_HOST`) with **HTTP 200, no EAI**; general internet (pypi.org) is **blocked** (DNS fail). So the Cortex Code CLI/SDK (which hits the account endpoint) likely needs **no EAI** — refines the earlier doc-based claim that REST/CLI require one. **An EAI is only needed for foreign hosts.** Confirm the full CLI path touches only the account host in the real container run.
- **Open — dual identity:** orchestrator SQL uses the SPCS session token (`ORCH_PROJ_<ID>`, least-priv, 1.6b); the CLI/SDK authenticates via a **PAT** (separate role). Scope the PAT least-privilege; the two identities must coexist.

## Governance + phases (decided 2026-06-30)
Authoritative permission matrix: `spec/Governance_Who_May_Do_What.md`. **Agents build & test; humans own the blast radius.**
- **FORBIDDEN to EVERY orchestrator agent (incl. the SPEC Judge), HITL-only, provisioned BEFORE the night run:** account parameters (`ALTER ACCOUNT`), security/external integrations (EAI, SECURITY/API/STORAGE INTEGRATION), network rules/policies, `MANAGE GRANTS` / grants to foreign principals, and `DROP`/`CREATE OR REPLACE` (no autonomous destruction).
- **Phase decomposition:** Phase 1 = agentic-loop rebuild (worker swap + gate generalization + 3 contract requirements). **Phase 2** (`spec/Phase2_Spec_Admission.md`) = SPEC Admission **before** the night run: a **SPEC Judge** (adversarial, read-only, advisory — proposes, never provisions) extracts infra requirements; a **deterministic verifier** (code, SHOW/DESCRIBE vs the live account — defaults vary per account!) is the authority; **HITL provisions** + approves the account-change manifest. **Phase 3** (`spec/Phase3_Deployment.md`) = deliverable = **deterministic GitHub repo** (idempotent DDL + roles-required list + account-change manifest + frozen tests), deployable anywhere; promotion/exposure is human-gated. GitHub = delivery artifact, never the loop.
- **Two modes** (set at SPEC handover): *restricted* → HITL pre-provisions all account objects; *isolated* → DEVELOPER may CREATE non-forbidden account objects via a custom role `ORCH_BUILDER_<ID>` (broad CREATE minus forbidden class, no DROP). Forbidden class is HITL-only in both modes; every account-level CREATE is recorded as idempotent DDL + manifest.
- **3 contract requirements (Phase 1):** (1) named identifiers (FQN) + resolution query for runtime-derived attrs (Class B, e.g. service ingress URL); (2) smoke + functional tests per artifact ("build an app" is inadmissible); (3) build (DEV, project-scoped) vs promotion (human-gated) split. Gate generalizes to test a tree and/or deployed objects (SQL assertions), held-out kept out of agent reach.

## LICENSE critical: LangGraph MIT only
- Use ONLY `langgraph` library (MIT)
- NEVER use `langgraph-api`, `langgraph-cli`, `langgraph dev`, `langgraph build` — these are Elastic License 2.0 (commercial key required)

## Multi-tenancy & safety (decided 2026-06-16) — supersedes earlier RAP/RLS note
- **Tenant = database.** Isolation via separate DBs, NOT Row Access Policies. RAP rejected: too much operational overhead (role/access mgmt on central team). Each DB = own namespace → DB-scoped objects can't collide.
- **Multiple independent instances per account** allowed (one DB = one instance), configured via .env (SF_DATABASE/SF_POOL/SF_ROLE_PREFIX) — same code, NO forks. (Forking the engine per project = rejected, causes code drift; isolate via config/multi-instance instead. See [[project-prepsmart]].)
- **Account-level objects** (compute pool, roles, EAIs) live outside the DB → can collide between instances. Tag ours with `COMMENT='managed-by:orchestrator;instance:<id>'`. Existing+ours → reuse; existing+foreign/untagged → **Exception, pipeline halts for user feedback** (no silent reuse).
- **Pipeline role (ORCH_RUNNER / ORCH_PROJ_*) has NO DROP right.** `CREATE OR REPLACE` (implicit drop) is forbidden for the pipeline — only CREATE / CREATE IF NOT EXISTS, versioned.
- **No autonomous drops.** Need to replace an object → version suffix `_V2/_V3`, loop continues (not an abort). Agent writes an append-only **cleanup report** + pre-generates a **cleanup script** (DROP statements) the USER runs after review. Deletion is always human-gated. (Exception: the one-time, ACCOUNTADMIN-authorized Paket 1.0 rename migration may drop the empty PREPSMART objects.)

## Feedback loop = Snowflake tables, NOT GitHub (portability)
The deterministic feedback loop runs entirely INTERNAL to Snowflake via the append-only tables (TASK_SPECS → Claude generates → TEST_RESULTS → gate → DEV_COMMENTS → retry). This is exactly WHY we chose append-only tables: external egress to GitHub needs an External Access Integration + network rule, which can be policy-blocked and "doesn't work everywhere." The table-based loop runs on any account/container with no egress. **Do NOT build GitHub egress into the core loop.** (Considered + rejected 2026-06-16.) GitHub push, if ever wanted, is an optional publish step — never the loop.

## Append-Only tables (no UPDATE, no DELETE ever)
Every change = new row. History is structural. RBAC trivially enforced: LEAD gets INSERT only.

```sql
CREATE VIEW TASK_SPECS_CURRENT AS
SELECT * FROM TASK_SPECS
QUALIFY ROW_NUMBER() OVER (PARTITION BY task_id ORDER BY created_at DESC) = 1;
```
Orchestrator reads only WHERE status = 'LOCKED'.

## Workflow roles (renamed 2026-06-16: PREPSMART_* → ORCH_*, prefix via SF_ROLE_PREFIX)
| Role | Rights |
|---|---|
| ORCH_LEAD | INSERT on TASK_SPECS + PROJECTS |
| ORCH_DEVELOPER | build project artifacts (agentic worker) under ORCH_PROJ_<ID> |
| ORCH_TESTER | derive/freeze tests (→ TEST_SPECS, 1.8) |
| ORCH_RUNNER | orchestrator service identity; assumes ORCH_PROJ_<ID> per task |
| ORCH_HUMAN_IN_LOOP | oversight/escalation; owns the blast radius (see [[governance]]/Governance spec) |

Plus per-project execution roles **ORCH_PROJ_<ID>** (least-priv, created by register_project). Authoritative permission matrix: `spec/Governance_Who_May_Do_What.md`.

## Orchestrator control-plane tables (the training-tool tables live in the separate PrepSmart repo now)
`ORCHESTRATOR.CORE`: TASK_SPECS (+project_id), PROJECTS (registry), TASK_SPECS_CURRENT (view). Per project in `ORCHESTRATOR.<ID>`: DEV_COMMENTS, TEST_RESULTS, RUNS (+ CODE_STAGE). Append-only. Component map: `docs/COMPONENT_AUDIT.md`.
