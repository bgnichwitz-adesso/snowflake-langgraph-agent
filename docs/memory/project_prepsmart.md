---
name: project-prepsmart
description: PrepSmart — daily AI learning companion + multi-tenant Streamlit-in-Snowflake app to train Lead Context Engineers on Azure AI Foundry evaluation
metadata: 
  node_type: memory
  type: project
  originSessionId: 6f1f11b8-8aba-4b15-9aee-e9e196b22c62
---

## ⚠️ Repo split (2026-06-15)
Two separate tools/repos now:
1. **Orchestrator** = this repo (`snowflake-langgraph-orchestrator`). Generic deterministic LangGraph orchestrator on Snowflake/SPCS. Phase 0 COMPLETE — see [[phase0-tasks]] + `phase0_report.md` + `docs/SESSION_PROTOCOL_2026-06-15.md`. Do NOT re-run Phase 0.
2. **PrepSmart training tool** = the learning companion (below). Its specs were moved OUT of this repo to `/home/gnichwitz/prepsmart-training/` (local only; user creates its repo ~2026-06-16). Keep training files/concepts out of the orchestrator repo.

## What PrepSmart is
Daily learning companion + management system to make the user the best Lead Context Engineer for Conversational Agents in insurance. Two tracked dimensions: (1) Knowledge, (2) Leadership (Literal Leadership).

**Why:** User has zero Azure AI Foundry knowledge and needs structured, measurable daily training with weekly tests.

## Three-layer architecture
1. **PrepSmart Project** — Living Context Document (Markdown) in Claude Project Knowledge, single source of truth
2. **Streamlit in Snowflake** — Multi-tenant app, calls Claude via Enterprise API key, hosts everything in Snowflake
3. **Mobile (Claude App)** — Always has full context via Living Context Document

## Learning system
- **Daily median target:** ~30 min/day (10–45 min corridor)
- **Weekly target:** ~210 min
- **Weekly test:** Sunday, ~30 min, evaluates Knowledge (official 7-group taxonomy) + Leadership
- **7-day Kickstart** (Microsoft only) → ongoing daily companion (then AWS comparatively)

## Content: Azure AI Foundry Evaluator Taxonomy
Official 7-group structure (NOT the simplified 3-group version often seen in blogs):
1. General purpose (2) | 2. Textual similarity (6) | 3. RAG (6) | 4. Risk & safety (9) | 5. Agent (9) | 6. Azure OpenAI graders (4) | 7. Custom (preview)
— 36 evaluators total

Priority for insurance RAG agent: Relevance, Groundedness, Task Completion, Safety (Group 4), Tool Call Accuracy

## Multi-tenancy
Variant C: B-capable from start, A-simple initially. Schema has TENANT_ID from day 1, one default tenant, org management activatable later without schema migration.
Data isolation via Snowflake Row Access Policies on TENANT_ID + USER_ID.

**How to apply:** Any implementation must carry TENANT_ID + USER_ID on all user-data tables. Content layer (evaluator docs) is global/readable by all.
