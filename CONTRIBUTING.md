# Contributing — Git Workflow

These rules are mandatory for all code changes in this repo (human or agent).

## Branching
- **Never commit directly to `main`.** Create a branch for every change.
- Branch naming: `phase<N>-<topic>` for phase work, `chore/<topic>`,
  `fix/<topic>`, or `feat/<topic>` otherwise.

## Commits = rollback points
- **Commit working code incrementally.** Each commit must be a known-good state
  you can safely roll back to — ideally one coherent unit per commit
  (e.g., one bootstrap package / one task) committed *after* its test passes.
- **Do not batch unrelated work** into a single commit.
- **Meaningful commit messages.** State what the change does and include the
  PASS evidence (version number, status, query result) that proves it works.
  Example:

  ```
  Phase 0 / Package 1: headless Snowflake auth + connection test

  PASS evidence: CURRENT_VERSION()=10.20.102, role ACCOUNTADMIN.
  ```

## Secrets & artifacts
- Never commit secrets. `.secrets/`, `*.pat`, `*.env`, `.venv/` are gitignored —
  keep them that way. Credentials (e.g. the PAT) live only in `.secrets/`.

## Pushing / PRs
- Push and open PRs only when asked. Keep `main` releasable.
