# Project instructions

## Git workflow (mandatory)
Follow `CONTRIBUTING.md` for all code changes: work on a branch (never commit to
`main`), commit working code incrementally as rollback points, use meaningful
commit messages that include PASS evidence, and never commit secrets.

## Snowflake auth (laptop scripts)
Headless auth uses a PAT at `.secrets/pat` (gitignored). Run scripts via the
venv: `.venv/bin/python scripts/<name>.py`. See `phase0_report.md` for details.

## Project memory — LOAD ON DEMAND (same authority as `~/.claude` memory)
`docs/memory/` is the versioned mirror of this project's session memory, so a fresh
clone or a colleague has the full ruleset (the live `~/.claude/.../memory/` copy is
local-only and not in git). **At the start of every session, read
`docs/memory/MEMORY.md` (the one-line index) and load the relevant entries on demand —
treat them with the SAME authority and the SAME auto-load-on-demand behaviour as the
`~/.claude` memory files.** Non-negotiable rules live there, in particular:
- `docs/memory/arch_principle_container_langgraph.md` — the orchestrator loop MUST run
  IN-CONTAINER and use LangGraph (a host/non-LangGraph loop is not a solution).
- `docs/memory/overview-html-upkeep.md` — regenerate `docs/overview.html` after EVERY step.
- `docs/memory/git_workflow.md` / `git_auth.md` / `headless_auth.md` — git + auth rules.
- `docs/memory/phase1_status.md` — current state / where to continue.

Keep the two copies in sync: the assistant updates the live `~/.claude` memory during a
session; re-copy it into `docs/memory/` (and commit) whenever a rule or status changes.
