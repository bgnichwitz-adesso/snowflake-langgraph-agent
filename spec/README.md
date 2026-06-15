# Specification — Snowflake LangGraph Orchestrator

This repo is the **orchestrator** only: a deterministic LangGraph orchestrator
that runs Claude as a pure code worker inside SPCS, calling Cortex over the
internal OAuth path, with hard test-gated pass/fail. It was split out from the
PrepSmart learning tool (first consumer); the training-tool specs now live in
their own repo.

| Doc | Content |
|---|---|
| `Agent-Dev-Prinzipien_Deterministischer-Orchestrator.md` | Architecture: deterministic orchestrator, test gate, Claude-as-worker via Cortex, SPCS, RBAC / append-only |
| `Phase0_Bootstrap_Tasks.md` | The 6 Phase 0 bootstrap packages (**COMPLETE** — see `../phase0_report.md`) |

**Where we are:** Phase 0 complete. Setup + run order in the top-level
`README.md`; session history in `../docs/`.
