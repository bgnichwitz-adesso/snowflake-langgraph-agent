# Project instructions

## Git workflow (mandatory)
Follow `CONTRIBUTING.md` for all code changes: work on a branch (never commit to
`main`), commit working code incrementally as rollback points, use meaningful
commit messages that include PASS evidence, and never commit secrets.

## Snowflake auth (laptop scripts)
Headless auth uses a PAT at `.secrets/pat` (gitignored). Run scripts via the
venv: `.venv/bin/python scripts/<name>.py`. See `phase0_report.md` for details.
