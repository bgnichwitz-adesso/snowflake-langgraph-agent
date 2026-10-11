---
name: git-auth
description: GitHub push/pull works headlessly via the store credential helper — no ! workaround needed
metadata: 
  node_type: memory
  type: project
  originSessionId: 2b145440-804c-4c3d-b27f-df03d873100a
---

GitHub auth is configured for headless use: `git config --global credential.helper store` with a classic PAT (repo scope) in `~/.git-credentials` (chmod 600). So `git push`/`git pull`/`git fetch` to `origin` (https://github.com/bgnichwitz-adesso/snowflake-langgraph-agent.git) run non-interactively from the agent shell — no need to ask the user to run pushes via `!`.

**How to apply:** Just `git push origin <branch>` directly. If it fails with auth, the PAT likely expired/was revoked — ask the user for a new GitHub PAT and overwrite `~/.git-credentials` (format `https://<user>:<PAT>@github.com`). Distinct from the Snowflake PAT in [[headless-auth]]. Follow [[git-workflow]] for branching/commit rules.
