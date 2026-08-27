# Component & Coherence Audit

**Date:** 2026-06-23 · Living reference: what each component is for, whether we
still need it after the **agentic-worker pivot**, and which milestone touches it.
Pivot context: `superpowers/specs/2026-06-28-agentic-worker-migration-design.md`,
memory `arch_decisions` / `phase1_status`, `../spec/Phase1_Orchestrator_Loop.md`.

Status legend: **KEEP** (unchanged) · **ADAPT** (changes at a milestone) ·
**NEW** (to be created) · **RETIRED** (removed this consolidation).

## Container code (`app/`)
| File | Purpose | Status |
|---|---|---|
| `orchestrator.py` | The deterministic LangGraph loop (1.6/1.6b) | **ADAPT** — M3/M5: `generate()` → agent worker; `run_tests` tests a tree; `State` carries workdir ref |
| `gate.py` | PASS/FAIL on exit code only — sole "done" authority | **KEEP** |
| `test_runner.py` | Runs pytest per task dir from mounted CODE_STAGE → TEST_RESULTS | **ADAPT** — M4: test a file tree, not one `solution.py` |
| `cortex_client.py` | One-shot `CORTEX.COMPLETE` (3-arg) → text+usage | **KEEP as legacy/fallback**; candidate for 1.8 TESTER generation. NOT the worker anymore |
| `stage_io.py` | Verifies stage volume-mount round-trip (1.4) | **KEEP** as a thin verify helper (agent now owns the writing) |
| `langgraph_flow.py` | Minimal one-node LangGraph→Cortex smoke; used by `healthcheck` container_e2e | **KEEP** for now → may be replaced by an agent smoke after M2 |
| `agent_worker.py` | Agentic worker wrapping the Cortex Code SDK `query()` with `output_format` | **NEW** — M3 (does not exist yet) |
| ~~`cortex_test.py`~~ | Phase-0 Paket-3 Cortex smoke | **RETIRED** — superseded by `cortex_client` self-test + healthcheck |

## Scripts (`scripts/`)
| File | Purpose | Status |
|---|---|---|
| `config.py` | Central config from `.env` (names, roles, helpers) | **ADAPT** — M3: add agent settings (model, max_turns, PAT env) |
| `sf.py` | Snowflake connection helper (PAT → headless) | **KEEP** |
| `p2_infra.py` | Create DB/schema/compute pool/image repo | **KEEP** (setup) |
| `p6_roles.py` | Workflow roles + TASK_SPECS/PROJECTS/view + grants | **KEEP** (setup) |
| `register_project.py` | Onboard a project: `ORCH_PROJ_<ID>` role, artifact schema, grants, PROJECTS row | **KEEP** |
| `build_push.sh`, `registry_login.sh`, `image_uri.py` | Image pipeline (derives registry host) | **KEEP** |
| `run_job.py` | Generic SPCS job-service runner | **ADAPT** — add PAT env for the SDK (M-series) |
| `healthcheck.py` | One-shot end-to-end health check, self-suspending | **ADAPT** — M1: also assert CLI + SDK present in image |
| `p1_connect.py` | Connection smoke | **KEEP** (handy; healthcheck also covers it) |
| `p14_stage_io.py` | Proof: stage I/O from container | **ADAPT** — M4: agent-produced files |
| `p15_test_gate.py` | Proof: runner + gate (pass/fail) | **ADAPT** — M4: artifact tree |
| `p16_loop.py` | Proof: full loop (solvable→DONE, impossible→NEEDS_HUMAN) | **ADAPT** — M5: agent worker |
| `p16b_role_scoping.py` | Proof: loop runs least-priv as `ORCH_PROJ_<ID>` | **ADAPT** — M6: dual identity (session token + PAT) |
| ~~`p0_enable_idtoken.py`~~ | Enable SSO id-token caching | **RETIRED** — PAT path chosen instead |
| ~~`p2_service.py`~~ | Phase-0 bootstrap READY service | **RETIRED** — concept dropped; healthcheck/p16 cover services |
| ~~`p3_cortex.py`~~ | Phase-0 Cortex-from-container proof | **RETIRED** — superseded by healthcheck |

## Docker
| File | Purpose | Status |
|---|---|---|
| `docker/Dockerfile` | Image: python + connector + langgraph + pytest/ruff | **ADAPT** — M1: add SDK + `cortex` CLI (~210 MB) + entrypoint (headless PAT connections.toml) |
| `docker/requirements.txt` | Pinned image deps | **ADAPT** — M1: add `cortex-code-agent-sdk` |

## Specs / docs (all KEEP; coherent set)
- `Phase0_Bootstrap_Tasks.md`, `../phase0_report.md` — **historical** (COMPLETE).
- `Phase1_Orchestrator_Loop.md` — the loop; pivot-reconciled (1.7 dropped, agentic worker = 1.7′, M1–M6).
- `Governance_Who_May_Do_What.md` — **authoritative** permission matrix (agents build/test; humans own blast radius).
- `Phase2_Spec_Admission.md` — SPEC Judge (advisory) + deterministic verifier + HITL provisioning, before a night run.
- `Phase3_Deployment.md` — deliverable = deterministic GitHub repo (idempotent DDL + roles-required + account-change manifest + frozen tests); promotion human-gated.
- `Agent-Dev-Prinzipien_…md` — dev principles; §7.3 corrected (tenant=DB, no RAP).
- `superpowers/specs/2026-06-28-agentic-worker-migration-design.md` — the M0–M6 plan.

## Coherence findings (status after this consolidation)
1. ✅ `Agent-Dev-Prinzipien` §7.3 stale RAP reference → corrected (tenant = database, no RAP).
2. ✅ `Phase1` loop diagram showed one-shot Cortex → updated to the agentic DEVELOPER node.
3. ✅ `healthcheck` control_plane asserted an exact role set (broke on `ORCH_PROJ_DEMO`) → subset check + reports project roles.
4. ✅ memory `arch_decisions` "5 roles" table said `PREPSMART_*` → updated to `ORCH_*` (metadata note).
5. ℹ️ Two worker paths (COMPLETE vs future agent) coexist **by design** — `cortex_client.py` clearly labeled legacy/fallback.

## Live Snowflake objects (account AWS_DE, verified 2026-06-23 via healthcheck)
DB `ORCHESTRATOR.CORE`; pool `ORCH_POOL_XS` (suspended); image repo + `orchestrator_base:latest`;
roles `ORCH_LEAD/_DEVELOPER/_TESTER/_RUNNER/_HUMAN_IN_LOOP` + `ORCH_PROJ_DEMO`;
`TASK_SPECS`+`PROJECTS`+`TASK_SPECS_CURRENT`; project `DEMO` (stand-in DB `DEMO_PROJ`,
fixture `DEMO_PROJ.PUBLIC.SAMPLE_DATA`). Healthcheck 5/5 OK.

## Forward path
M1 ✅ → M2 ✅ → M3 ✅ (`app/agent_worker.py` + `app/agent_env.py` wired into `generate`; visible/held-out split)
→ **M4 (next: re-verify 1.4/1.5 — p14/p15 — with agent artifacts)** → M5 (e2e loop)
→ M6 (run under `ORCH_PROJ_<ID>`; PAT/dual-identity dropped; consider held-out physical isolation) →
1.8 (TESTER generation) → Phase 2 (SPEC admission) → Phase 3 (deployment repo).
New app modules: `agent_worker.py` (SDK worker), `agent_env.py` (shared oauth bootstrap),
`agent_hello.py` (M2 proof), `agent_smoke.py` (M1 proof). CLI pinned `1.1.66+001753.801adc2b71d7`.
OPEN hardening: held-out tests physically on the mounted stage the agent shell can reach — isolate later.

## Maintenance rule
**Regenerate `docs/overview.html` after EVERY completed step** (Paket/M-milestone/consolidation)
so it always mirrors current state, and commit it with that step. It is the primary
quick-overview artifact. Serve to Windows from WSL: `.venv/bin/python -m http.server 8000
--bind 0.0.0.0` in `docs/` → `http://localhost:8000/overview.html`.
