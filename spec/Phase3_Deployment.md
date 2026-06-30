# Phase 3 — Deployment (Spec)

Status: **✏️ design 2026-06-30** (no code yet). Defines the orchestrator's **final
deliverable** and how a built system is rolled out. Permissions per
[`Governance_Who_May_Do_What.md`](./Governance_Who_May_Do_What.md).

## Principle
The true output of a night run is **not** "objects mutated in one account" — it is a
**deterministic GitHub repo** that reproduces the system on **any** environment. GitHub
is the **delivery artifact, never the loop** (consistent with the no-egress-in-loop
decision). Rollout is a **human-gated** step, not an autonomous agent action.

## The deliverable repo contains
1. **Idempotent DDL/scripts** for every artifact the system needs — project-scoped
   **and** any account-level objects created (`CREATE … IF NOT EXISTS`, versioned; no
   DROP/OR REPLACE).
2. **Roles-required list** — exactly which roles/privileges a target environment must
   grant to deploy + run the system (so a new env knows what to set up).
3. **Account-change manifest** — a quickly-graspable, append-only list of **every
   account-level change** (what, why, which privilege). Generated from the actual ops,
   reconciled against the DDL. This is the HITL review surface.
4. **The frozen tests** (smoke + functional) so the deployed system can be re-verified
   on the target env.

## Who deploys / grants (challenged + decided)
- **Build & self-test** = DEVELOPER agent, autonomous, least-priv, project-scoped (+ in
  isolated mode, non-forbidden account objects via the custom role).
- **Promotion / exposure** = **human-gated**: account-level provisioning, the forbidden
  class (security/network/integrations/grants), and granting access to external
  consumers. The agent **proposes** (emits idempotent script + manifest); **HITL runs
  it** with elevated rights — same pattern as the cleanup-script rule.
- No agent grants access to foreign principals or opens network/auth surface. Ever.

## Rollout to a new environment
1. Clone the repo.
2. Run Phase-2 admission against the **target** account (defaults differ!) → gap report.
3. HITL provisions the roles-required list + forbidden-class prerequisites.
4. Apply the idempotent DDL.
5. Run the frozen tests (smoke + functional) → green = deployed.

## Pass-gate (Phase 3 done)
A repo that, applied to a fresh compliant environment via the steps above, reproduces
the system and passes its frozen tests — with the account-change manifest reviewed and
approved by HITL.

## Open points
- Repo layout (DDL ordering / dependency graph; how account vs project DDL is separated).
- Smoke-testing a **public** endpoint from inside SPCS (foreign host → needs the network
  story; ties to Phase 2 forbidden class).
- Versioning of redeployments (the `_V2/_V3` rule for replaced objects).
