# Session Protocol — 2026-06-15

Purpose: a pickup record so the next session (human or agent) knows what exists,
what was decided, and where to continue — **without re-running Phase 0**.

## TL;DR — current state
- **Phase 0 is COMPLETE.** All 6 bootstrap packages PASS (evidence:
  `phase0_report.md`). The Snowflake objects already exist — do not recreate.
- The repo is **parameterized** (everything account-specific in `.env`) and has
  onboarding docs (`README.md`, `setup.sh`).
- The repo was **split**: it now holds the **orchestrator only**. The PrepSmart
  learning-tool specs were moved out (kept locally at
  `/home/gnichwitz/prepsmart-training/`, own repo to be created).
- Compute pool is **SUSPENDED** (zero cost). Nothing is running.
- Nothing pushed yet; work lives on local branches (see below).

## What was built this session
1. **Headless auth** — laptop scripts auth via a PAT at `.secrets/pat`
   (EXTERNALBROWSER can't cache headlessly in WSL2). `scripts/sf.py` +
   `scripts/config.py`.
2. **Phase 0, packages 1–6** — connection, SPCS infra + image + service (READY),
   Cortex from container (internal OAuth, no EAI), langgraph in image, one-node
   LangGraph flow ("SYSTEM OK"), and 5 roles + append-only TASK_SPECS + grants +
   TASK_SPECS_CURRENT view. Per-package commits on `phase0-bootstrap`.
3. **Portability** — central config from `.env`, registry host derived from the
   live image repository (`image_uri.py`), podman/docker support, pinned deps,
   README/setup. Verified end-to-end on this account.
4. **Repo split** — orchestrator files only; training files preserved locally.

## Snowflake objects that exist (account AWS_DE / ADESSO-AWS_DE)
> Renamed in Phase 1 / Paket 1.0 (2026-06-16): the PrepSmart-flavored names below
> were migrated to neutral names and the old PREPSMART objects dropped.
- DB `ORCHESTRATOR`, schema `CORE`
- Compute pool `ORCH_POOL_XS` (CPU_X64_XS, auto-suspend 600s) — SUSPENDED
- Image repo `ORCHESTRATOR.CORE.IMAGES`; image `orchestrator_base` (tag: latest)
- 5 roles `ORCH_*` (LEAD/DEVELOPER/TESTER/RUNNER/HUMAN_IN_LOOP); tables
  `TASK_SPECS` (+project_id, INSERT→LEAD only) + `PROJECTS`; view `TASK_SPECS_CURRENT`
- Old PREPSMART DB / `PREPSMART_*` roles / `PREPSMART_POOL_XS` — dropped (were empty).

## Key decisions (rationale in phase0_report.md / arch spec)
- **Cortex via SQL `SNOWFLAKE.CORTEX.COMPLETE`** over the connector, NOT the
  snowpark `Complete(...)` wrapper (lighter image, stable contract). Phase 1:
  move to the 3-arg JSON form (messages, temperature=0, capture `usage`).
- **PAT auth** instead of EXTERNALBROWSER caching (the latter needs
  `ALLOW_ID_TOKEN` and didn't cache reliably here).
- **langgraph (MIT) library only** — never langgraph-api/cli (Elastic 2.0).
- Orchestrator runs as **job-services** (exit → pool auto-suspends); the
  Package-2 long-running `BOOTSTRAP_SVC` was only to prove READY and was dropped.

## Branch state (nothing pushed)
- `chore/split-and-protocol` ← latest (this split + docs), built on:
- `feat/portable-setup` (all Phase 0 + parameterization + onboarding)
- `chore/git-workflow-docs` (CONTRIBUTING.md + CLAUDE.md, off main)
- `phase0-bootstrap` (Phase 0 only)
- `main` (specs only — pre-split)
Intended consolidation: merge `chore/split-and-protocol` (carries everything via
`feat/portable-setup`) and `chore/git-workflow-docs` into `main`, then push.

## Where to continue — Phase 1
Pick from `phase0_report.md` open points. Likely first steps:
- Implement the orchestrator loop (load_task → claude_generate → run_tests →
  gate → commit/next | feed-back/retry; MAX iterations → STOP) with LangGraph
  checkpointing on a mounted stage.
- Cortex 3-arg JSON form (temperature=0, usage tracking).
- Remaining tables + Row Access Policies (multi-tenant TENANT_ID + USER_ID).
- PAT lifecycle (expiry/rotation; least-privilege role instead of ACCOUNTADMIN).
- Optional: generalize PrepSmart-flavored object names.
