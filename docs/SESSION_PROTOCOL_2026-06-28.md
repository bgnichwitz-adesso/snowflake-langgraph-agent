# Session Protocol — 2026-06-28

Purpose: pickup record of a **design + spike** session. No production code changed
yet. We re-verified the real Phase-1 state, found a logging/observability dead end,
and pivoted the worker architecture. Two empirical spikes were run.

## TL;DR
- **Real state corrected:** last commit is `2f426ba` (Paket 1.6b). Local == origin/main,
  0 ahead/behind — **no missing commit**. `phase1_status.md` memory was stale
  (said "next = register_project 1.1"); the actual frontier is 1.6b done, 1.7/1.8 open.
- **1.7 (checkpointing/resume) reframed and shelved.** For an overnight, multi-task
  autonomous run the right recovery granularity is the *task*, derivable from the
  append-only log — not per-iteration LangGraph checkpoints. We chose **not** to build it now.
- **Major pivot:** replace the single-shot `COMPLETE` code-worker with an **agentic
  worker** (Option C/A). The one-shot *guesses* and degrades over iterations; an agent
  that writes+runs+iterates converges. **Deterministic gate stays the heart**
  (SPEC→DEVELOPER→TESTER, frozen tests decide). Only the worker changes.
- **Chosen worker:** the **Cortex Code Agent SDK** (`cortex-code-agent-sdk`), because it
  already knows Snowflake (deploy, Streamlit-in-Snowflake, Snowpark, dbt…). Hand-rolling
  a Snowflake-naive ReAct agent would reinvent that and be weaker.
- **Egress myth busted (empirically):** an SPCS container **reaches its own account
  endpoint without an EAI** (HTTP 200). General internet is blocked. So the SDK/CLI path
  likely needs **no External Access Integration** — only the account host, which is reachable.

## Spikes run (evidence)
1. **Laptop SDK spike** (`scratchpad/spike_hello.py`): drove `cortex_code_agent_sdk.query()`
   headless → agent created `hello.py`, ran it, returned `ResultMessage(subtype=success)`.
   Proves the SDK works programmatically/headless and produces+executes code.
2. **SPCS egress probe** (job `EGRESS_PROBE_JOB`, existing `latest` image):
   ```
   INTERNAL_HOST(env)=rq11769.eu-central-1.snowflakecomputing.com
   EGRESS_OK   https://rq11769.eu-central-1.snowflakecomputing.com  status=200
   EGRESS_FAIL https://pypi.org  URLError: Name or service not known
   ```
   Proves: account endpoint reachable from SPCS without EAI; general internet blocked.

## Key research findings (via Cortex Code plugin, doc-grounded)
- `SNOWFLAKE.CORTEX.COMPLETE`/`AI_COMPLETE`: **no native tool-use**; options are only
  `temperature, top_p, max_tokens, guardrails, response_format`. `response_format`
  (JSON schema, constrained decoding) **is** supported — our structured-artifact lever.
- Raw SQL `COMPLETE` does **not** auto-log to `SNOWFLAKE.LOCAL.AI_OBSERVABILITY_EVENTS`.
  Auto-logging paths: Cortex Agents, **Cortex Code**, TruLens-instrumented apps.
  (So the SDK/Cortex-Code path *may* auto-log — to be verified empirically.)
- Cortex Code Agent SDK: `output_format` (JSON-schema) gives a validated
  `ResultMessage.structured_output` — exactly the testable artifact the gate needs.

## Decisions
- **D1** Worker = Cortex Code Agent SDK (agentic), gate stays deterministic. (Option C/A)
- **D2** No EAI assumed necessary (account host reachable); confirm in the real container run.
- **D3** Recovery is task-granular via the append-only log; no per-iteration checkpointing (drop 1.7 as written).
- **D4** Observability: prefer our own append-only tables; re-evaluate AI_OBSERVABILITY auto-log once measured on the SDK path.

## Open points (carry forward)
- **Dual identity / least-privilege:** orchestrator SQL uses the SPCS session token
  (`ORCH_PROJ_<ID>`, 1.6b); the CLI/SDK uses a **PAT** (separate role). The PAT must be
  scoped least-privilege and the two must coexist. (touches 1.6b)
- **Multi-file artifact:** the agent produces a *tree*, not one `solution.py`; test runner
  + gate must handle that and keep frozen tests separate from agent output.
- **Other egress hosts:** confirm the CLI only needs the account host (no blocked update/telemetry/model hosts).
- **Image size:** CLI tree is ~210 MB → larger image, longer build/push/pool-start.
- **Deployment (NEXT-NEXT topic):** if the orchestrator builds whole systems, *who deploys
  the built system, how?* To be specified after the rebuild spec.

## Next steps (ordered)
1. **Review/update the Phase-1 spec for the rebuild** (`spec/Phase1_Orchestrator_Loop.md`
   + `spec/Agent-Dev-Prinzipien_*.md`): record the agentic-worker decision, deprecate the
   COMPLETE-worker and the checkpointing line, add the new gated packages.
2. **Rethink the deployment spec** (how orchestrator-built systems get deployed; who/how).
3. Then execute the migration plan (`docs/superpowers/specs/2026-06-28-agentic-worker-migration-design.md`).

## Cost hygiene
Compute pool `ORCH_POOL_XS` auto-suspends after 600 s idle. The probe job resumed it;
it self-suspends. Verify SUSPENDED at session end.
