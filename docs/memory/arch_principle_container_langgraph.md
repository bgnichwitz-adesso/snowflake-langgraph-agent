---
name: arch-principle-container-langgraph
description: Non-negotiable — the orchestrator loop MUST run in-container AND use LangGraph
metadata:
  node_type: memory
  type: feedback
  originSessionId: 77947bf2-76b5-4cd9-aead-c9a6c0de6d42
  modified: 2026-10-10T14:41:32.666Z
---

**Non-negotiable architecture principle (user, 2026-10-10):** "Eine Lösung ohne Container und ohne LangGraph ist keine Lösung." The deterministic orchestrator loop MUST run **in-container** (SPCS) AND be built with **LangGraph** (the `StateGraph` in `app/orchestrator.py`). A host-driven plain-Python loop is NOT an acceptable solution.

**Why:** it's the core purpose/identity of the project (deterministic LangGraph orchestrator on SPCS), not just an implementation detail.

**How to apply:**
- Form B (host-driven plain loop) was REVERTED. **Form A is now implemented + verified (2026-10-10):**
  `app/orchestrator.py` (LangGraph StateGraph, runs in-container as ORCH_PROJ) launches the DEV/TESTER
  work as nested `ORCH_DEV`/`ORCH_TEST` child SPCS jobs (nested `EXECUTE JOB SERVICE` — proven by
  `scripts/p_a_nested_probe.py`). Thin launcher `scripts/run.py` (no host loop). Do NOT reintroduce a host loop.
- Never use `langgraph-api`/`langgraph-cli` / LangGraph Studio-prod / LangSmith (enterprise key + egress) — MIT `langgraph` StateGraph only.
- UI/monitoring must be free-commercial + egress-free: **Streamlit-in-Snowflake** over the append-only tables (recommended); Langfuse self-hosted (MIT core) optional. See [[arch-decisions]], [[phase1-status]].
