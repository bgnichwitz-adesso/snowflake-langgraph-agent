# Agent-Entwicklungsprinzipien — Deterministischer Orchestrator
### Teil von PrepSmart · Stand: 13. Juni 2026 · für die Implementierung mit Claude Code

> **Kernprinzip:** *Determinismus schlägt Selbstdisziplin.* Claude entscheidet **nie**, ob etwas „fertig" ist — genau da hat es sich bisher rausgeredet und Fehler ignoriert. Ein deterministischer Orchestrator entscheidet anhand **harter, immer gleicher Testergebnisse**. Claude wird zum reinen Code-Worker.
>
> Markierung: **📘** = aus offizieller Quelle (verlinkt) · **✏️** = unsere Projektentscheidung.

---

## 1. Rollenverteilung (✏️)
| Komponente | Tech | Aufgabe | Darf NICHT |
|---|---|---|---|
| **Orchestrator** | Python + `langgraph` (MIT) | Kontrollfluss, State, Loop, Gating. Einzige Instanz, die „bestanden/nicht bestanden" entscheidet. | — |
| **Test-Gate** | deterministisch: `pytest`, `ruff`, `mypy`, Build-Exit-Code + dbt-Tests/SQL-Assertions gegen Snowflake-Dev-DB | liefert hartes Pass/Fail | LLM-Urteil enthalten |
| **Claude (Worker)** | Cortex Inference (intern) | bekommt Spec + letzten Testoutput, gibt Code/Diff zurück | „fertig" erklären; Tests bewerten |

## 2. Der Loop (📘-fundiert, ✏️-umgesetzt)
Als `langgraph`-Graph mit konditionalen Kanten und hartem Iterations-Limit:
```
load_task → claude_generate → run_tests → [pass?]
   ├─ pass → commit → next_task
   └─ fail → feed_test_output_back → claude_generate   (loop)
              └─ if iterations ≥ MAX → STOP + report
```
- Das Gate ist **deterministischer Code**, kein LLM. Fehler-Ignorieren ist strukturell unmöglich.
- 📘 Microsoft/Anthropic-Prinzip: *„address the root cause, don't suppress the error"* und *„if you can't verify it, don't ship it."* → [Claude Code Best Practices](https://code.claude.com/docs/en/best-practices)

## 3. Aufgabenpaket-Workflow (✏️ — dein Zielablauf)
1. **Abends (1–2 h), gemeinsam:** Pakete definieren. Spec-first. 📘 Muster: Claude per `AskUserQuestion` interviewen lassen, dann self-contained `SPEC.md` schreiben — *„name the files/interfaces, state what is out of scope, end with an end-to-end verification step."* → [Best Practices](https://code.claude.com/docs/en/best-practices)
2. **Definition of Done pro Paket:** konkrete, ausführbare Verifikationskriterien (welche Tests, welcher Exit-Code, welche dbt-Tests grün).
3. **Über Nacht:** Orchestrator arbeitet die Pakete autonom ab (SPCS Job-Service).
4. **Morgens:** Ergebnis + **Evidence** (Testoutput, Diffs, Review-Findings) — 📘 *„show evidence rather than asserting success."*

## 4. Disziplin-Bausteine (📘 aus der Recherche, eingebettet)
- **TDD erzwingen:** Tests zuerst, müssen erst **failen**, dann grün. Red Flags des Superpowers-Frameworks: Tests, die beim ersten Lauf bestehen; „should/probably/seems"; „just this once". Ziel: *den Agenten daran hindern, sich aus den Regeln herauszureden.* → [Superpowers (Anthropic Plugin)](https://claude.com/plugins/superpowers)
- **Spec-first & verifizierbare Kriterien** (siehe §3).
- **Adversarialer Review in frischem Kontext:** nach Fertigstellung ein separater Claude-Call/Subagent, der **nur** Diff + SPEC sieht und gegen die Kriterien prüft (Lücken, keine Stilfragen). → [Best Practices](https://code.claude.com/docs/en/best-practices)
- **Least privilege:** Orchestrator und Tests bekommen nur die Rechte, die das Paket braucht.
- **Frischer Kontext pro Task** verhindert Context-Drift bei langen Läufen.

## 5. Architektur in Snowflake (📘-fundiert, ✏️-entschieden)
- **Hosting:** Snowpark Container Services (SPCS). **Job-Service** für den Über-Nacht-Lauf (run-to-completion); optional Long-running Service (auto-restart). → [SPCS-Überblick](https://docs.snowflake.com/en/developer-guide/snowpark-container-services/overview)
- **Claude über Cortex — intern, ohne EAI:** OAuth-Token unter `/snowflake/session/token` + `SNOWFLAKE_HOST` → der host-Parameter hält die Verbindung intern, **kein Egress**. Aufruf via `snowflake.cortex.Complete(model, prompt, session=...)`. → [Verbindung aus SPCS](https://docs.snowflake.com/en/developer-guide/snowpark-container-services/additional-considerations-services-jobs) · [Cortex REST API](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-rest-api)
- **Test-Gate gegen Snowflake-Dev-DB:** Container hat interne Credentials → dbt-Tests/SQL-Assertions laufen direkt.
- **State/Checkpoints + Code-Repo:** auf gemountete Stages → Lauf ist fortsetzbar (nutzt `langgraph`-Checkpointing).
- **Private Link:** sichert weiterhin den Außenzugang; der interne Cortex-Call ist davon unberührt (kein Internet).
- **⚠️ Lizenzgrenze (✏️):** Nur die `langgraph`-**Library** (MIT) nutzen — **nicht** `langgraph-api` / `langgraph dev|build` (Elastic License 2.0, kommerzieller Key nötig). Orchestrator läuft als normaler Python-Prozess.
- **⚠️ Trade-off Cortex (✏️):** an in Cortex verfügbare Claude-Modelle/Regionen + Cortex-Rate-Limits gebunden (429 → exponentielles Backoff). Native Anthropic-API nur falls neuestes API-only-Modell nötig → dann EAI + Secret für `api.anthropic.com`.

## 6. Anti-Patterns, die wir aktiv vermeiden (📘)
- **Trust-then-verify-Lücke** → Fix: immer Verifikation; ohne Check kein Ship.
- **Fehler unterdrücken statt Root Cause** → Fix: Gate verlangt grünen Lauf, nicht „Error weg".
- **Kitchen-sink-Session / Endlos-Exploration** → Fix: enges Scoping pro Paket, frischer Kontext, Subagents für Recherche.
- **Überladene CLAUDE.md** → Fix: kurz halten; was deterministisch sein muss, gehört in einen Hook/ins Gate, nicht in advisory Text.
→ [Best Practices](https://code.claude.com/docs/en/best-practices)

## 7. Task-Verwaltung — RBAC & Immutabilität in Snowflake (✏️)

### 7.1 Prinzip: Append-Only / Insert-Only
Kein UPDATE, kein DELETE — je. Jede Änderung = neue Row. History ist inhärent in der Tabellenstruktur. Keine Stored Procedures für Immutabilität nötig. RBAC wird trivial: LEAD bekommt nur INSERT — fertig.

**Tabellenstruktur `TASK_SPECS`:**
```
task_id | version | status   | spec_content | created_by | created_at
T001    | 1       | DRAFT    | …            | LEAD       | 09:00
T001    | 2       | APPROVED | …            | LEAD       | 10:00
T001    | 3       | LOCKED   | …            | LEAD       | 11:00
```

**„Aktuell"-View:**
```sql
CREATE VIEW TASK_SPECS_CURRENT AS
SELECT * FROM TASK_SPECS
QUALIFY ROW_NUMBER() OVER (
  PARTITION BY task_id
  ORDER BY created_at DESC) = 1;
```

**Orchestrator liest ausschließlich `WHERE status = 'LOCKED'`** — selbst wenn LEAD danach einen neuen DRAFT einfügt, läuft der aktuelle Task unberührt.

### 7.2 Fünf Rollen & Objekte

| Objekt | LEAD | DEVELOPER | TESTER | ORCHESTRATOR | HUMAN_IN_LOOP |
|---|---|---|---|---|---|
| `TASK_SPECS` | INSERT | SELECT | SELECT | SELECT | SELECT |
| `DEV_COMMENTS` | — | INSERT + SELECT | — | — | SELECT |
| `TEST_RESULTS` | — | SELECT | INSERT + SELECT | SELECT | SELECT |

**Rollenbegründung:**
- `LEAD` — definiert und sperrt Tasks. Einzige Schreibberechtigung auf Specs.
- `DEVELOPER` — liest Tasks, schreibt + liest eigene Kommentare.
- `TESTER` — liest Tasks, schreibt Test-Ergebnisse für Dev.
- `ORCHESTRATOR` — Service-Rolle für den LangGraph-Job. Liest nur LOCKED Tasks + Test-Ergebnisse. Kein Schreibrecht auf Specs.
- `HUMAN_IN_LOOP` — Oversight. Liest Dev-Kommentare (Eskalationskanal) + alle Specs.

### 7.3 Konsistenz mit dem Multi-Tenant-Modell
`TASK_SPECS`, `DEV_COMMENTS`, `TEST_RESULTS` tragen `TENANT_ID` + `USER_ID` — Row Access Policies analog zu §4a der Haupt-Spec.

## 8. Offene Punkte für die Implementierung heute Abend
1. SPCS-Setup: Compute Pool, Image-Repo, Job-Service-YAML.
2. `langgraph`-Graph: Knoten (load_task / generate / test / review / commit) + MAX_ITERATIONS.
3. Test-Gate-Skript: pytest/ruff/mypy + dbt-Tests gegen Dev-DB.
4. Cortex-Session-Helper (OAuth-Token, host-intern).
5. SPEC.md-Vorlage + Definition-of-Done-Vorlage pro Paket.
6. Stage-Mounts für State/Repo (Fortsetzbarkeit).
7. DDL: `TASK_SPECS`, `DEV_COMMENTS`, `TEST_RESULTS` mit `TENANT_ID`/`USER_ID` + `TASK_SPECS_CURRENT`-View.
8. RBAC: 5 Rollen anlegen, Grants setzen (INSERT-only für LEAD, SELECT für alle anderen auf `TASK_SPECS`).

---

## Quellen-Block (täglich zu prüfen · Primärquelle: Anthropic & Snowflake offiziell)
| Quelle | Link | Zuletzt geprüft |
|---|---|---|
| Claude Code — Best Practices | https://code.claude.com/docs/en/best-practices | 13.06.2026 |
| Superpowers (Anthropic Plugin) | https://claude.com/plugins/superpowers | 13.06.2026 |
| SPCS — Considerations (OAuth-Token/host) | https://docs.snowflake.com/en/developer-guide/snowpark-container-services/additional-considerations-services-jobs | 13.06.2026 |
| Cortex REST API | https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-rest-api | 13.06.2026 |
| LangGraph LICENSE (MIT) | https://github.com/langchain-ai/langgraph/blob/main/LICENSE | 13.06.2026 |
