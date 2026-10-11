---
name: git-workflow
description: "User's required git workflow — branch for changes, commit working code with meaningful messages as rollback points"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 2b145440-804c-4c3d-b27f-df03d873100a
---

For any code changes: work on a **branch** (not main), and **commit working code incrementally** with **meaningful commit messages** that serve as explicit rollback points.

**Why:** The user wants safe, recoverable checkpoints — each commit should be a known-good state to roll back to.

**How to apply:** Create a feature branch before editing. Commit each coherent working increment (e.g., per package/task) once it passes its test, with a message stating what it does AND the PASS evidence. Don't batch unrelated work into one commit. Established in Phase 0: branch `phase0-bootstrap`, one commit per bootstrap package. See [[phase0-tasks]].
