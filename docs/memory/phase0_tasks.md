---
name: phase0-tasks
description: Phase 0 bootstrap — 6 sequential packages to get a working LangGraph+Cortex orchestrator running in SPCS. Each has a hard test gate.
metadata: 
  node_type: memory
  type: project
  originSessionId: 6f1f11b8-8aba-4b15-9aee-e9e196b22c62
---

## Status (as of 2026-06-15)
✅ COMPLETE — all 6 packages PASS. Branch `phase0-bootstrap`, evidence in `phase0_report.md`. See [[git-workflow]] and [[headless-auth]]. Open points for Phase 1 are listed in the report.

**Global rules:** STOP on FAIL. Show evidence. Fix root cause. Scope each package exactly.

## Packages
| # | Task | Pass condition |
|---|---|---|
| 1 | Snowflake connection from laptop | `SELECT CURRENT_VERSION()` returns version number |
| 2 | SPCS container (Python + snowflake-connector) | `SHOW SERVICES` → status = READY |
| 3 | Cortex reachable from container | `cortex.Complete("claude-sonnet-4-6", "say: HELLO")` returns response |
| 4 | LangGraph installed in container | `python -c "import langgraph; print(langgraph.__version__)"` succeeds |
| 5 | First LangGraph flow with Cortex | Graph output contains "SYSTEM OK" |
| 6 | Roles + grants in Snowflake | 5 PREPSMART_* roles + INSERT-only on TASK_SPECS for LEAD + TASK_SPECS_CURRENT view |

**Stop point:** After Package 3 is a clean stop point if time runs short.

**Deliverable:** `phase0_report.md` with status + evidence per package + open points for Phase 1.

**Why:** This phase establishes the base infrastructure. Nothing else can run until these 6 packages are green.
