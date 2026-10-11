---
name: overview-html-upkeep
description: "Standing rule — regenerate docs/overview.html after EVERY completed step; it's the go-to visual overview"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 2b145440-804c-4c3d-b27f-df03d873100a
  modified: 2026-08-26T14:33:59.453Z
---

**Rule (user, standing):** After EVERY completed step/milestone (a Paket, an M-milestone, a consolidation, any change to architecture/status/roadmap/components), **regenerate `docs/overview.html`** so it always reflects the current state, then commit it with that step. Keep it in mind every session — it is the user's primary quick-overview artifact.

**Why:** The user comes back after weeks-long gaps and needs an instant visual overview without reading markdown. A stale overview defeats the purpose.

**How to apply:**
- `docs/overview.html` is a single self-contained (no-CDN, offline) page rendered from `docs/COMPONENT_AUDIT.md` + `spec/*` + this memory. Update: header + footer commit hash, status tiles, loop/arch if changed, component keep/adapt/retire table, roadmap (✅/◀ next), live objects, healthcheck count.
- Serve to the Windows host from WSL: `.venv/bin/python -m http.server 8000 --bind 0.0.0.0` in `docs/`, open `http://localhost:8000/overview.html` (WSL2 forwards localhost). See [[phase1-status]] for current milestone. Follow [[git-workflow]] to commit.
