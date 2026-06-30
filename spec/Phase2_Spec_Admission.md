# Phase 2 — SPEC Admission & Pre-Qualification (Spec)

Status: **✏️ design 2026-06-30** (no code yet). Runs **before** a SPEC is handed to
the night-run orchestrator (Phase 1). Permissions per
[`Governance_Who_May_Do_What.md`](./Governance_Who_May_Do_What.md).

## Why this phase exists
A SPEC like "build an app" is not admissible: you can't derive tests or know what
infrastructure it needs. And much of Snowflake "works by default" — but **defaults
vary per account and must be verified, not assumed**. So before any autonomous night
run we (1) make the SPEC testable, (2) extract the exact infrastructure it requires,
(3) verify the live account, (4) let HITL provision the prerequisites + the forbidden
class. The night run then receives a **verified SPEC + a manifest of provisioned
parameters**.

## Inputs
- The candidate SPEC (acceptance contract per task).
- Target account + **mode** (`restricted` | `isolated`) — set at handover.

## Steps
### Step 1 — SPEC Judge (agent, advisory, read-only)
An adversarial agent in a fresh context (per Agent-Dev-Prinzipien §4) checks the SPEC
and emits a **structured requirements manifest**. It does **not** decide "ready" and
**provisions nothing** (forbidden class included). It checks:
- **Verification surface (Phase-1 contract rule):** every artifact names its objects
  (FQN) and declares smoke tests (infra stands) + functional tests (behaves), incl.
  the **resolution query** for any runtime-derived attribute (Class B — e.g. a service
  ingress URL via `SHOW ENDPOINTS`).
- **Infrastructure inventory:** every object the SPEC implies, classified as
  project-scoped / account-level / **forbidden class** (security/network/integration/
  grants/DROP).
- **Testability gaps:** any artifact lacking a named identifier or a test → flagged.

Output: `requirements_manifest` (append-only): objects, identifiers, resolution
queries, tests, classification, gaps.

### Step 2 — Deterministic verifier (code, the hard truth)
For each required capability/object, run `SHOW`/`DESCRIBE`/parameter queries against
the **live account** and diff against the manifest → **gap report** (PRESENT / MISSING /
MISCONFIGURED). This is code, not LLM judgment — it is the authority on account state.
(A SPEC-driven extension of `scripts/healthcheck.py`.)

### Step 3 — HITL provisioning gate
HITL reviews the gap report + the **forbidden-class list**, then **provisions** what is
missing (account parameters, EAIs/integrations, network rules, grants, custom role) and
re-runs Step 2 until green. HITL approves the **account-change manifest**.

### Output handed to Phase 1
- The **verified SPEC** (admitted).
- A **provisioned-parameters manifest** (what HITL set up + identifiers/resolution
  queries the night run will rely on). DEVELOPER gets **read** on these params for
  self-diagnosis (exception, not its job — Step 2 already proved correctness).

## Determinism guardrail
The Judge **proposes**; the deterministic verifier + HITL **decide**. No LLM ever
silently declares a SPEC admissible. The Judge's own output is itself checked: every
named artifact must resolve via a real `SHOW`, every test must reference a real
identifier.

## Pass-gate (Phase 2 done)
Admitted SPEC + green Step-2 verifier + HITL-approved account-change manifest. Only then
may the night run start.

## Open points
- Exact `requirements_manifest` schema (objects, identifiers, resolution queries, tests).
- How the verifier enumerates "capabilities" generically (per object type → which SHOW/DESCRIBE).
- Where the manifest lives (control-plane table vs. the deliverable repo — likely both).
