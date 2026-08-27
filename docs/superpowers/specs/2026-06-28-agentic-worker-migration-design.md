# Agentic-Worker Migration — Design & Plan

**Date:** 2026-06-28 · **Status:** design (no code changed) · supersedes the
single-shot `COMPLETE` worker and the 1.7 checkpointing line.

## Goal
Replace the one-shot `COMPLETE` code-worker with an **agentic worker** (Cortex Code
Agent SDK) that writes/runs/iterates within a task and hands back a **fixed,
schema-validated artifact**. The deterministic outer loop and gate
(SPEC→DEVELOPER→TESTER, frozen tests decide) are unchanged — only the DEVELOPER
node's *brain* changes. We pass our SPEC building blocks through the orchestrator
→ SDK → Cortex Code CLI.

## Architecture (unchanged vs changed)
```
load_task → [DEVELOPER node]            ← CHANGED: one-shot COMPLETE  →  agentic SDK loop
              (agent writes code,
               runs scratch, iterates,
               returns artifact)
          → run_tests (FROZEN gate)     ← mostly unchanged (now tests a tree, not one file)
          → gate (exit-code only)       ← UNCHANGED
          → PASS:DONE | FAIL:feedback→DEVELOPER (≤MAX_ITER) | NEEDS_HUMAN  ← UNCHANGED
```

## Code-change map (exactly what changes)

| File | Change | Why |
|---|---|---|
| `docker/requirements.txt` | **add** `cortex-code-agent-sdk` (+resolved deps) | SDK in image |
| `docker/Dockerfile` | **add** the `cortex` CLI tree (~210 MB) + entrypoint that writes `~/.snowflake/connections.toml` from env (`CORTEX_PAT/ACCOUNT/USER`) | SDK spawns the CLI; headless PAT auth |
| `app/agent_worker.py` | **NEW** — wraps `query()` with `CortexCodeAgentOptions(cwd, permission_mode='bypassPermissions', max_turns, output_format=<schema>, connection=...)`; returns validated `structured_output` | the agentic worker + fixed artifact |
| `app/orchestrator.py` `generate()` | **rewrite body** — call `agent_worker.run(spec, visible_tests, last_output, cwd=<iter workdir>)` instead of `cortex_complete`+`_extract_code`; keep DEV_COMMENTS insert (log agent summary+usage) | swap worker |
| `app/orchestrator.py` `_extract_code()` | **remove** | replaced by structured_output |
| `app/orchestrator.py` `run_tests()` | **adapt** — no longer writes `solution.py` (agent already wrote files into the workdir); copy frozen tests in + run pytest on the tree | multi-file artifact |
| `app/orchestrator.py` `State` | `code:str` → carry the **workdir/artifact ref** | agent owns the files |
| `app/cortex_client.py` | **keep** (legacy / may serve the 1.8 TESTER generation or fallback); mark not-the-worker | don't break other uses |
| `scripts/config.py` | **add** agent settings (model, max_turns, PAT env name) | config |
| `scripts/run_job.py`, `scripts/p16b_role_scoping.py`, loop launcher | **add** `CORTEX_PAT`(+account/user) env to the job spec (prefer SPCS secret over plain env); keep the session-token path for the orchestrator's own SQL | dual auth |
| `app/stage_io.py` | role shrinks — agent's `cwd` = mounted CODE_STAGE workdir; persistence already via volume; keep as a thin verify helper | agent does the writing |
| `scripts/healthcheck.py` | **extend** — assert CLI present + SDK import in image | regression guard |

## Test re-run matrix (what must be re-verified)

| Paket | Existing test | Why it must re-run | New gate |
|---|---|---|---|
| 1.3 Cortex node | `cortex_client` self-test | superseded by the agent worker | **NEW:** agent builds hello-world **in SPCS**, returns `structured_output`, no EAI |
| 1.4 stage I/O | `p14_stage_io.py` | agent now writes to mounted `cwd` | agent-produced files persist on `CODE_STAGE`, readable |
| 1.5 runner+gate | `p15_test_gate.py` | artifact is a tree, not one `solution.py` | pass-task→PASS, fail-task→FAIL on agent output + frozen tests |
| 1.6 loop | `p16_loop.py` | `generate` is now the agent | end-to-end: solvable→DONE, impossible→NEEDS_HUMAN |
| 1.6b role-scoping | `p16b_role_scoping.py` | **dual identity** (session token + PAT) | loop runs least-priv; PAT scoped least-priv; `RUNS=DONE` |
| infra | `healthcheck.py` | new image deps | OK with CLI+SDK present |

Already verified this session: **egress without EAI** (re-confirm full CLI path touches only the account host).

## Migration sequence (gated, each a commit/rollback point)
- **M0 ✅ (done):** egress proven (no EAI); laptop SDK spike builds+runs hello-world.
- **M1 ✅ (done 2026-06-23):** agent-SDK image built. `docker/requirements.txt` +`cortex-code-agent-sdk==1.0.2`; `docker/Dockerfile` installs the `cortex` CLI at build time via `curl -LsS https://ai.snowflake.com/static/cc-scripts/install.sh | sh` (+curl/ca-certs, then purged) and sets `PATH`/`CORTEX_CODE_CLI_PATH`. New `app/agent_smoke.py` + healthcheck `cortex_cli` check. Proven in-container (no EAI, no auth): `Cortex Code v1.1.66` + SDK import + `AGENT_SMOKE_OK`; healthcheck 6/6; langgraph_flow still green. (Entrypoint/PAT deferred to M2, as reviewed.)
- **M2 ✅ (done 2026-08-27):** container hello-world — `app/agent_hello.py`: SDK→CLI→`agent:run` built `hello.txt` in SPCS, `ResultMessage(subtype=success, is_error=False)`, **no EAI, no PAT**. Auth = **internal SPCS OAuth token via a runtime-written `connections.toml`** (`authenticator=oauth`, `token_file_path=/snowflake/session/token`, selected by `connection="spcs"` + `SNOWFLAKE_HOME=/tmp/sfhome`). Offline flags set (`--no-auto-update`, `COCO_*_DISABLED`, `COCO_CLI_CONNECTION_OVERRIDES_INFERENCE=1`). **Key fix:** env `SNOWFLAKE_TOKEN` alone was NOT enough — the CLI resolves the agent connection from `connections.toml`. Also pinned the CLI (see below). Healthcheck 6/6.
- **M3 ✅ (done 2026-08-27):** `app/agent_worker.py` (SDK, `output_format`→`structured_output`
  {summary,entry_point,files,ready} + manifest.json fallback) wired into
  `orchestrator.generate()`; `_extract_code`/single-file prompt removed; `State.code`→`workdir`.
  Agent works in a LOCAL cwd (`/tmp/orch/<task>/iter-N`); tree copied to stage for audit.
  `run_tests` runs **visible vs held-out separately** — only visible output is fed back to
  the agent (held-out details never leave); gate = both green. Shared auth in `app/agent_env.py`.
  Proven: task-add→DONE via agent (structured_output); task-impossible→NEEDS_HUMAN@3. Healthcheck 6/6.
  **Two bugs found & fixed during M3:** (a) feedback leaked full pytest output incl. held-out →
  now visible-only; (b) toy "impossible" fixture was gameable by a degenerate `__eq__` → hardened to
  typed asserts (`type(r) is int and r==N`). **OPEN (hardening, later): held-out tests physically
  live on the mounted stage the agent's shell can reach — for a *gameable* task a clever agent could
  read them. Fix later via no-mount/transient-fetch or a separate gate container (defense-in-depth).**
- **M4:** re-verify 1.4 + 1.5 with agent artifacts.
- **M5:** end-to-end loop (1.6) on the agent worker.
- **M6:** ~~dual identity + least-priv PAT~~ **DROPPED** — M2 proved the CLI uses the internal SPCS token (single identity). Remaining M6 work: run the agent under `ORCH_PROJ_<ID>` (mechanism from 1.6b), no PAT.
- **then 1.8** (TESTER generation) on the new base.

## Open design points (resolve in spec review, not now)
1. ✅ **Dual identity / least privilege — RESOLVED 2026-08-27 (M2):** NO PAT, NO dual identity. The Cortex CLI authenticates with the **internal SPCS OAuth token** (connections.toml `authenticator=oauth` + `token_file_path=/snowflake/session/token`), i.e. the SAME identity as the orchestrator SQL. Least-priv = run the agent under `ORCH_PROJ_<ID>` (1.6b mechanism).
2. ✅ **Multi-file artifact / `output_format`** — RESOLVED 2026-06-23 (see `spec/Phase1_Orchestrator_Loop.md` → "Agentischer Worker — festgelegte Details"): schema `{summary, entry_point, files[], ready}`; **no thread-resume across outer iterations** (fresh agent invocation seeded from durable state each round).
3. **Observability** — measure whether SDK-headless auto-logs to `AI_OBSERVABILITY_EVENTS`; else our own append-only tables.
4. **Security** — agent runs arbitrary bash (`bypassPermissions`) inside the container; bounded by container grants.
5. **Image size / pool start** — ~210 MB CLI tree.
6. **PAT lifecycle** — expiry/rotation, SPCS secret vs env.

## Next steps (ordered, per session)
1. ✅ **Spec set updated for the rebuild** (2026-06-30): `spec/Phase1_Orchestrator_Loop.md`
   (worker pivot + 3 contract requirements + gate generalization, 1.7 dropped),
   **NEW** `spec/Governance_Who_May_Do_What.md`, `spec/Phase2_Spec_Admission.md`,
   `spec/Phase3_Deployment.md`; memory `arch_decisions`/`phase1_status` updated.
2. **Resolve open design points** in those specs (dual identity / PAT least-priv,
   `TEST_SPECS` table for 1.8, `requirements_manifest` schema, multi-file/SQL gate).
3. Execute M1→M6 (start: build agent-SDK image; container hello-world in SPCS, no EAI).
