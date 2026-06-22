# Phase 1 — Orchestrator Loop (Spec)

Status: **Planungs-/Bau-Phase** (Stand 2026-06-16). Phase 0 ist abgeschlossen
(`../phase0_report.md`). Diese Spec beschreibt den eigentlichen Orchestrator:
den deterministischen, tabellengetriebenen Feedback-Loop — **komplett intern in
Snowflake, kein GitHub-Egress** (bewusste Architekturentscheidung, läuft überall).

---

## Architektur

### Zwei Rollen-Ebenen
1. **Workflow-Rollen (generisch, orchestrator-weit):**
   `ORCH_LEAD`, `ORCH_DEVELOPER`, `ORCH_TESTER`, `ORCH_RUNNER`,
   `ORCH_HUMAN_IN_LOOP`. Wer mit dem Control-Plane interagiert; `ORCH_RUNNER` =
   Service-Identität des Loops.
2. **Projekt-Ausführungsrollen (pro Projekt):** `ORCH_PROJ_<PROJECT_ID>`.
   Damit arbeitet `ORCH_RUNNER` *in* einem Projekt. Wird an `ORCH_RUNNER`
   granted (Rollen-Hierarchie) → der Runner kann sie annehmen.

### Control-Plane vs. Artefakte
- **Control-Plane (zentral):** `ORCHESTRATOR.CORE`
  - `PROJECTS` — Registry (welches Projekt, Beschreibung, welche Rolle, wo).
  - `TASK_SPECS` (+ `project_id`) + `TASK_SPECS_CURRENT` View.
- **Artefakte (pro Projekt getrennt):** Schema `ORCHESTRATOR.<PROJECT_ID>`
  - `DEV_COMMENTS`, `TEST_RESULTS` (append-only)
  - Stage `CODE_STAGE` (generierter Code, je `<task_id>/<iter>/`)
- **Projekt-DB selbst:** bleibt im Besitz des Projekt-Teams. Orchestrator ist
  **Gast**: `ORCH_PROJ_<ID>` bekommt nur die nötigen Grants darauf.

### Projekt-Registry `PROJECTS` (append-only)
| Spalte | Zweck |
|---|---|
| `project_id` | Schlüssel, z. B. `PREPSMART` |
| `description` | Was das Projekt ist (Kontext bei jeder Aufgabe) |
| `execution_role` | `ORCH_PROJ_<ID>` — Rolle für dessen Tasks |
| `project_database` / `project_schema` | wo der Projektcode/-ressourcen liegen |
| `artifact_schema` | `ORCHESTRATOR.<PROJECT_ID>` |
| `code_stage` | `@ORCHESTRATOR.<PROJECT_ID>.CODE_STAGE` |
| `status`, `created_at`, `created_by` | Audit |

### Task → Projekt
`TASK_SPECS.project_id` → beim Laden joint der Orchestrator auf `PROJECTS`,
kennt Beschreibung + `execution_role` + Orte, macht `USE ROLE <execution_role>`
und arbeitet scoped. Deterministisch, keine Rätsel.

---

## Multi-Tenancy & Sicherheit (Instanz-Modell)

### Tenant = Datenbank (kein RAP)
- Isolation läuft über **getrennte Datenbanken**, nicht über Row Access Policies.
  RAP ist operativ teuer (Rollen-/Access-Management beim zentralen Team) → wird
  bewusst **nicht** verwendet. Jede DB = eigener Namespace → DB-Objekte können
  nicht kollidieren.
- **Mehrere unabhängige Instanzen pro Account** sind erlaubt (eine DB = eine
  Instanz). Konfiguriert über `.env` (`SF_DATABASE`, `SF_POOL`,
  `SF_ROLE_PREFIX` …) — selber Code, keine Forks.

### Account-Level-Objekte = Kollisionsrisiko → Exception
- DB-/Schema-scoped (DB, Schema, Image-Repo, Tabellen, Stages, Secrets,
  Network Rules) sind pro Instanz isoliert.
- **Account-Level** (Compute Pool, Rollen, External Access Integrations) liegen
  außerhalb der DB → können zwischen Instanzen kollidieren.
- Unsere Account-Objekte werden getaggt: `COMMENT =
  'managed-by:orchestrator;instance:<id>'`.
  - existiert + **unseres** → ok (reuse).
  - existiert + **fremd/ungetaggt** → **Exception**: Pipeline hält an, braucht
    User-Eingriff/Feedback. **Kein** stiller Reuse.

### Pipeline-Rolle: kein DROP, kein OR REPLACE
- `ORCH_RUNNER` / `ORCH_PROJ_<ID>` haben **kein DROP-Recht** (Schutz).
- `CREATE OR REPLACE` ist implizit ein DROP → für die Pipeline **verboten**. Nur
  `CREATE` / `CREATE IF NOT EXISTS`, ggf. versioniert.

### Statt Drop: Versionierung + human-gated Cleanup
- Müsste der Orchestrator ein Objekt ersetzen → **Versions-Suffix `_V2/_V3/…`**,
  Loop läuft weiter (**kein** Abbruch).
- Der Agent schreibt einen **Cleanup-Bericht** (append-only, in
  `ORCHESTRATOR.<PROJECT_ID>` / Stage): welche alten Versionen zur Löschung
  anstehen + warum.
- Dazu erzeugt er **vorab ein Cleanup-Script** (idempotente `DROP`-Statements).
  Der **User** führt es nach Prüfung mit erhöhten Rechten selbst aus. Löschung
  ist immer human-gated.

### Loop
```
load_task (LOCKED, + PROJECTS-Lookup, USE ROLE execution_role)
  → claude_generate (Cortex, schreibt Code → CODE_STAGE, Begründung → DEV_COMMENTS)
  → run_tests (Container holt Code vom Stage, pytest/ruff, Exit-Code+Log → TEST_RESULTS)
  → [gate: liest NUR Exit-Code aus TEST_RESULTS]
       ├─ pass → Status done → next_task
       └─ fail → TEST_RESULTS-Feedback → claude_generate (loop)
                  └─ iterationen ≥ MAX → STOP + Report
```
LangGraph-Checkpointing auf Stage → resümierbar. Gate = einzige Wahrheit
(Exit-Code), kein LLM-Urteil.

---

## Gated Pakete

| # | Paket | Pass-Gate |
|---|---|---|
| **1.0 ✅** | **Eigenes Zuhause (Rename-Migration):** DB `ORCHESTRATOR`, Schema `CORE`, Pool `ORCH_POOL_XS`, Repo `ORCHESTRATOR.CORE.IMAGES`, `ORCH_*`-Workflow-Rollen, `PROJECTS` + `TASK_SPECS`(+project_id) + View. Image neu pushen. **Alte PREPSMART-Objekte droppen.** | ✅ Neue Objekte da, Grants korrekt (INSERT nur LEAD), alte weg, Job läuft auf neuem Image |
| **1.1 ✅** (+1.2) | **Projekt-Registry + `register_project`** (`scripts/register_project.py`): legt `ORCH_PROJ_<ID>`-Rolle an (getaggt, Kollisions-guard), Artefakt-Schema `ORCHESTRATOR.<ID>` + `CODE_STAGE` + `DEV_COMMENTS` + `TEST_RESULTS`, grantet auf existierende Projekt-DB + Artefakt-Schema, grantet Rolle an `ORCH_RUNNER`, schreibt `PROJECTS`-Zeile | ✅ `DEMO` registriert: Rolle an RUNNER granted, PROJECTS-Zeile da, Artefakt-Schema + Tabellen + Stage da |
| **1.2 ✅** | *(in 1.1 enthalten)* Per-Projekt `DEV_COMMENTS`, `TEST_RESULTS`, `CODE_STAGE` im Artefakt-Schema | ✅ via register_project angelegt |
| **1.3 ✅** | **Cortex-Generierungs-Node** (`app/cortex_client.py`): `cortex_complete(messages, temperature=0)` via 3-arg JSON-Form (PARSE_JSON binds) → Text **+ usage** | ✅ Job lieferte text='GEN OK', usage prompt=22/completion=6/total=28 |
| **1.4 ✅** | **Stage-I/O aus Container** (`app/stage_io.py`): CODE_STAGE als Volume gemountet, Code nach `<task>/<iter>/` schreiben + zurücklesen | ✅ roundtrip_ok + Datei persistiert auf `@…DEMO.CODE_STAGE` (LIST verifiziert). *(Rollen-Scoping: in 1.6)* |
| **1.5 ✅** | **Test-Runner + Gate** (`app/test_runner.py` + `app/gate.py`): Code vom gemounteten Stage, pytest, Exit-Code+Log → `TEST_RESULTS`; Gate entscheidet nur über Exit-Code | ✅ task-pass→PASS (exit 0), task-fail→FAIL (exit 1); pytest+ruff im Image |
| **1.6 ✅** | **LangGraph-Loop** (`app/orchestrator.py`, EIN Container): load_task (+PROJECTS) → generate (cortex) → write Code+Tests auf Stage → run_tests → gate → [PASS:RUNS=DONE \| FAIL:DEV_COMMENTS-Feedback→generate], MAX_ITER (.env, Default 10) → STOP + Report (RUNS=`NEEDS_HUMAN`). Held-out-Tests: sichtbar im Prompt, held-out nur fürs Gate. Tests **fix vorgegeben** (simuliert TESTER). `RUNS`-Tabelle = Lauf-Ergebnis (TASK_SPECS bleibt LEAD-immutable). | ✅ task-add→DONE@iter0; task-impossible→NEEDS_HUMAN@3 (held-out fing return 4); append-only Spur |
| **1.6b ✅** | **Rollen-Scoping** (least-privilege): Launch-Kette User→`ORCH_RUNNER`→`ORCH_PROJ_<ID>`→EXECUTE JOB SERVICE (Owner=PROJ, Job im Artefakt-Schema). `register_project` grantet PROJ: USAGE Pool+Warehouse, READ Image-Repo, CREATE SERVICE, SELECT view+PROJECTS. Kein ACCOUNTADMIN mehr. | ✅ `running as role: ORCH_PROJ_DEMO` im Log, RUNS=DONE (`scripts/p16b_role_scoping.py`) |
| **1.7** | **End-to-end als Job-Service** | echter Lauf auf 1 Task, State in Tabellen/Stage, resümierbar |
| **1.8** | **TESTER-Generierungsschritt** (Separation of Duties): `ORCH_TESTER` leitet aus dem LEAD-Akzeptanzvertrag Tests ab, friert sie ein (DEV read-only), inkl. held-out. | aus Spec generierte, eingefrorene Tests; DEVELOPER kann sie nicht ändern |

**Querschnitt (parallel/später):** Account-Objekt-Tagging + Kollisions-Exception,
no-DROP-Pipeline-Rolle, Versionierung + Cleanup-Report/-Script (siehe
„Multi-Tenancy & Sicherheit"), PAT-Lifecycle + Least-Privilege statt
ACCOUNTADMIN. (Kein RAP — Tenant = Datenbank.)

---

## Globale Regeln (wie Phase 0)
STOP bei FAIL · Evidence zeigen · Root Cause · Scope einhalten · kein nächstes
Paket ohne grünen Test. Branch + Commit je Paket (siehe `../CONTRIBUTING.md`).
