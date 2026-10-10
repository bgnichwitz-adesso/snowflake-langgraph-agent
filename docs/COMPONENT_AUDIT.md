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
| `orchestrator.py` | In-container LangGraph loop (1.6/1.6b) | **LEGACY** — superseded by the host-driven `scripts/run_loop.py` (M6/B, Form B); kept for reference |
| `agent_job.py` | DEV-job entrypoint (M6/B): runs AS `ORCH_DEV` in its own SPCS job; reads spec from the exchange stage, runs the tool-sandboxed agent (file tools + SQL, no Bash), writes artifact back | **M6/B ✅ NEW** |
| `tester_job.py` | TESTER-job entrypoint (1.8): runs AS `ORCH_TEST`; authors `test_visible.py`+`test_heldout.py` from the spec, writes them to the exchange stage (SoD: no build) | **1.8 ✅ NEW** |
| `gate.py` | PASS/FAIL on exit code only — sole "done" authority | **KEEP** |
| `agent_worker.py` | Agentic worker (Cortex Code SDK `query()`, `output_format`→structured_output + manifest fallback); **tool-sandboxed** (`can_use_tool`: file tools only, cwd-jailed, no shell/SQL) | **M3/M4 ✅** |
| `agent_env.py` | Shared auth bootstrap (oauth `connections.toml`, SPCS token) | **M3 ✅ NEW** |
| `cortex_client.py` | One-shot `CORTEX.COMPLETE` (3-arg) → text+usage | **KEEP as legacy/fallback**; candidate for 1.8 TESTER generation. NOT the worker anymore |
| `langgraph_flow.py` | Minimal one-node LangGraph→Cortex smoke; used by `healthcheck` container_e2e | **KEEP** |
| `agent_hello.py` / `agent_smoke.py` | M2 hello-world proof / M1 offline import+CLI proof | **KEEP** (proofs) |
| ~~`test_runner.py`~~ / ~~`stage_io.py`~~ | old single-file pytest / stage round-trip | **DELETED** — folded into `orchestrator.run_tests` + agent owns writing |
| ~~`cortex_test.py`~~ | Phase-0 Paket-3 Cortex smoke | **RETIRED** — superseded by `cortex_client` self-test + healthcheck |

## Scripts (`scripts/`)
| File | Purpose | Status |
|---|---|---|
| `config.py` | Central config from `.env` (names, roles, helpers) | **ADAPT** — M3: add agent settings (model, max_turns, PAT env) |
| `sf.py` | Snowflake connection helper (PAT → headless) | **KEEP** |
| `p2_infra.py` | Create DB/schema/compute pool/image repo | **KEEP** (setup) |
| `p6_roles.py` | Workflow roles + TASK_SPECS/PROJECTS/view + grants | **KEEP** (setup) |
| `register_project.py` | Onboard a project: roles `ORCH_PROJ_<ID>` (gate), `ORCH_DEV_<ID>` (dev build+SQL), reserved `ORCH_TEST_<ID>`; artifact schema + `TEST_VISIBLE`/`TEST_HELDOUT`; **M6/B:** exchange schema `<ID>_XCHG` + stage (cross-granted both), ORCH_DEV build grants + service-execution | **M6/B ✅** |
| `run_loop.py` | **Host/runner-driven loop (Form B):** launch DEV job (ORCH_DEV) → pull artifact from exchange stage → gate as ORCH_PROJ (held-out) → RUNS | **M6/B ✅ NEW** |
| `run_tester.py` | **Host step (1.8):** launch TESTER job (ORCH_TEST) → read generated test files → insert into `TEST_VISIBLE`/`TEST_HELDOUT` (host-mediated). Run before `run_loop.py` | **1.8 ✅ NEW** |
| `build_push.sh`, `registry_login.sh`, `image_uri.py` | Image pipeline (derives registry host) | **KEEP** |
| `run_job.py` | Generic SPCS job-service runner | **ADAPT** — add PAT env for the SDK (M-series) |
| `healthcheck.py` | One-shot end-to-end health check, self-suspending | **ADAPT** — M1: also assert CLI + SDK present in image |
| `p1_connect.py` | Connection smoke | **KEEP** (handy; healthcheck also covers it) |
| `p_m4_agent.py` | Proof: agent code artifacts — multi-file (`app.py`+`mathutil.py`)→DONE+persisted; feedback-driven convergence (unguessable sentinel, iter0 FAIL→DONE) | **M4 ✅ NEW** |
| `p_m4_guard.py` | Proof (local, no credits): tool-sandbox deny-logic — denies Bash/SQL/session-token/outside-cwd/`..`-traversal, allows only cwd file tools (11/11) | **M4 ✅ NEW** |
| `p_m6_formb.py` | Proof (Form B, host loop): task-feedback→iter0 FAIL then DONE (host-side convergence); task-heldonly→NEEDS_HUMAN (held-out unreachable by ORCH_DEV) | **M6/B ✅ NEW** |
| ~~`p_m4_leak.py` / `p_m6_sql_probe.py` / `p_m6_devtoken_probe.py`~~ | PAT-era leak/SQL/token probes | **DELETED (M6/B)** — superseded by `p_m6_formb.py` (PAT approach dropped) |
| `p16_loop.py` | Proof: full loop (solvable→DONE, impossible→NEEDS_HUMAN); seeds tests into `TEST_VISIBLE`/`TEST_HELDOUT` | **LEGACY** (in-container loop) |
| `p16b_role_scoping.py` | Proof: loop runs least-priv as `ORCH_PROJ_<ID>` (container owned by project role; in-container gate reads held-out via the M6 grant) → DONE | **M6 ✅** |
| ~~`p14_stage_io.py`~~ / ~~`p15_test_gate.py`~~ | old stage-I/O / gate proofs | **DELETED** — superseded by `p16*` + `p_m4_agent` |
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
M1 ✅ → M2 ✅ → M3 ✅ → M4 ✅ (agent code artifacts; held-out in separate tables + tool-sandbox) →
M5 ✅ → M6 ✅ (in-container loop least-priv) → **M6/B ✅ (agent SQL via its OWN `ORCH_DEV` SPCS job;
host-driven loop `run_loop.py`; held-out unreachable by RBAC; no PAT — network policy blocks PAT from
SPCS, the OAuth token is exempt)** → **1.8 (next: TESTER generation, role `ORCH_TEST_<ID>` reserved)** →
Phase 2 (SPEC admission) → Phase 3 (deployment repo).
**1.8 ✅** — TESTER agent (`ORCH_TEST_<ID>`) authors frozen visible+held-out tests from the spec
(SoD); `tester_job.py` + `run_tester.py`. **NEXT = Phase 2 (SPEC admission)**, incl. human review of
generated tests before they are frozen.
M6/B note: the gate runs host-side (host needs `pytest`); a dedicated gate container is a later
hardening; `orchestrator.py`/`p16*` remain as the legacy in-container path.
New app modules: `agent_worker.py` (SDK worker, tool-sandboxed), `agent_env.py` (shared oauth bootstrap),
`agent_hello.py` (M2 proof), `agent_smoke.py` (M1 proof). CLI pinned `1.1.66+001753.801adc2b71d7`.
RESOLVED (M4) — TWO independent layers, both verified: (a) held-out off the mounted stage (separate
tables + transient gate materialization) defeats a filesystem hunt on its own; (b) agent tool-sandbox
blocks shell/SQL/path-escape. Checks: `p_m4_guard.py` (deny-logic 11/11, local), `p_m4_leak.py` enforce
(held-out-only unguessable value → NEEDS_HUMAN, guard wired), `p_m4_leak.py AGENT_SANDBOX=observe`
(decisive control: an UNBLOCKED agent actively hunts the FS for the tests — 11 Bash searches incl. the
gate dir — yet still can't reach held-out), `p_m4_agent.py` (convergence). The adversarial hunt is REAL,
not hypothetical. HONEST CAVEAT: the old stage-mounted design (removed) was never retested with an
unguessable value; the `42`-sentinel runs were inconclusive. Established: the CURRENT design does not
leak a held-out-only value.

## Maintenance rule
**Regenerate `docs/overview.html` after EVERY completed step** (Paket/M-milestone/consolidation)
so it always mirrors current state, and commit it with that step. It is the primary
quick-overview artifact. Serve to Windows from WSL: `.venv/bin/python -m http.server 8000
--bind 0.0.0.0` in `docs/` → `http://localhost:8000/overview.html`.
