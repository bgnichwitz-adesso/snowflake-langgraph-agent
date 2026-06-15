# Phase 0 — Bootstrap Tasks
### Direkte Anweisungen für Claude Code · Heute Abend 13.06.2026

> **Was dieses Dokument ist:** Anweisungen für Claude Code auf dem Laptop — NICHT für den Orchestrator. Der Orchestrator existiert noch nicht. Claude Code ist heute Abend selbst der Ausführende.
>
> **Ziel:** Am Ende dieser Phase steht ein lauffähiger Orchestrator in einem SPCS-Container der Claude über Cortex intern erreicht und einen minimalen LangGraph-Flow ausführen kann. Das ist die Basis für alle weiteren Nacht-Läufe.

---

## Globale Regeln für Claude Code (gelten für alle Pakete)

1. **STOP bei FAIL** — kein nächstes Paket ohne grünen Test. Fehlermeldung vollständig ausgeben.
2. **Evidence zeigen** — nicht „hat funktioniert" behaupten. Immer den tatsächlichen Output zeigen (Versionsnummer, Status, Response).
3. **Root Cause, nicht Symptom** — Fehler beheben, nicht unterdrücken.
4. **Scope einhalten** — jedes Paket macht genau was drin steht, nichts mehr.
5. **Kein nächstes Paket ohne explizite PASS-Meldung** des vorherigen.

---

## Paket 1 — Snowflake-Verbindung testen

**Aufgabe:** Verbindung vom Laptop zu Snowflake aufbauen und verifizieren.

**Schritte:**
1. `snowflake-connector-python` installieren falls nicht vorhanden
2. Verbindung mit Account-Credentials aufbauen
3. Query ausführen: `SELECT CURRENT_VERSION()`

**Test (Pass/Fail):**
```
Query gibt Snowflake-Versionsnummer zurück → PASS
Zeige: Versionsnummer + Account-Name als Evidence
Jeder Fehler → FAIL + vollständige Fehlermeldung + STOP
```

**Scope — macht NICHT:**
Kein Container, keine Rollen, keine Tabellen.

---

## Paket 2 — SPCS Container erstellen

**Aufgabe:** Compute Pool anlegen, Image Repository erstellen, minimales Docker-Image bauen (Python + snowflake-connector), pushen und als Job-Service starten.

**Schritte:**
1. Compute Pool anlegen (`CREATE COMPUTE POOL`)
2. Image Repository anlegen
3. Minimales Dockerfile bauen: `python:3.11-slim` + `snowflake-connector-python`
4. Image pushen ins Snowflake Image Repository
5. Service-YAML erstellen und Service starten

**Test (Pass/Fail):**
```
SHOW SERVICES gibt Status = READY → PASS
Zeige: Service-Name + Status als Evidence
Jeder andere Status oder Fehler → FAIL + STOP
```

**Scope — macht NICHT:**
Kein LangGraph, kein Cortex-Test, keine Applikationslogik.

---

## Paket 3 — Cortex aus Container erreichbar testen

**Aufgabe:** Aus dem laufenden Container heraus Cortex via internem OAuth-Token aufrufen.

**Schritte:**
1. OAuth-Token aus `/snowflake/session/token` lesen
2. Snowflake-Session mit `SNOWFLAKE_HOST` + Token aufbauen (interner Pfad, kein Egress)
3. `snowflake.cortex.Complete("claude-sonnet-4-6", "say: HELLO", session=session)` aufrufen

**Test (Pass/Fail):**
```
Cortex gibt eine Antwort zurück → PASS
Zeige: vollständige Antwort als Evidence
Netzwerkfehler / Auth-Fehler / leere Antwort → FAIL + STOP
```

**Scope — macht NICHT:**
Kein LangGraph, keine Applikationslogik.

**⚠️ Hinweis:** Kein External Access Integration nötig — der Aufruf läuft intern über `SNOWFLAKE_HOST`. Falls doch ein Netzwerkfehler auftritt: prüfen ob `SNOWFLAKE_HOST` korrekt gesetzt ist.

---

## Paket 4 — LangGraph in Container installieren

**Aufgabe:** `langgraph`-Library (MIT) im Container-Image installieren und import-fähig machen.

**Schritte:**
1. `langgraph` zu `requirements.txt` hinzufügen
2. Docker-Image neu bauen und pushen
3. Container neu starten

**Test (Pass/Fail):**
```python
python -c "import langgraph; print(langgraph.__version__)"
```
```
Gibt Versionsnummer aus → PASS
Zeige: Versionsnummer als Evidence
ImportError oder anderer Fehler → FAIL + STOP
```

**Scope — macht NICHT:**
Kein Flow, keine Cortex-Integration, kein Orchestrator-Logik.

**⚠️ Lizenz:** Nur `langgraph` (MIT). Nicht `langgraph-api`, nicht `langgraph-cli`. Kein `langgraph dev` oder `langgraph build`.

---

## Paket 5 — Erster LangGraph Flow mit Cortex

**Aufgabe:** Minimalen LangGraph-Graph bauen der einen einzigen Knoten hat: Claude über Cortex aufrufen und Antwort zurückgeben.

**Schritte:**
1. Graph mit einem Knoten `call_claude` definieren
2. Knoten ruft `snowflake.cortex.Complete` auf (OAuth-Token-Pfad aus Paket 3)
3. Graph mit Test-Input ausführen: `{"prompt": "say: SYSTEM OK"}`

**Test (Pass/Fail):**
```
Graph läuft durch, Output enthält "SYSTEM OK" → PASS
Zeige: vollständigen Graph-Output als Evidence
Graph-Fehler / Cortex-Fehler / falscher Output → FAIL + STOP
```

**Scope — macht NICHT:**
Kein Loop, kein Test-Gate, keine echten Tasks — nur Proof of Concept.

---

## Paket 6 — Rollen + Grants anlegen

**Aufgabe:** Die 5 Projektrollen in Snowflake anlegen und Grants auf `TASK_SPECS` setzen.

**Schritte:**
1. Rollen anlegen: `PREPSMART_LEAD`, `PREPSMART_DEVELOPER`, `PREPSMART_TESTER`, `PREPSMART_ORCHESTRATOR`, `PREPSMART_HUMAN_IN_LOOP`
2. `TASK_SPECS`-Tabelle anlegen (Append-Only, mit `status`-Spalte + `tenant_id` + `user_id`)
3. Grants setzen: nur `PREPSMART_LEAD` bekommt INSERT, alle anderen SELECT
4. `TASK_SPECS_CURRENT`-View anlegen

**Test (Pass/Fail):**
```sql
SHOW ROLES LIKE 'PREPSMART_%';          -- 5 Rollen → PASS
SHOW GRANTS ON TABLE TASK_SPECS;        -- INSERT nur für LEAD → PASS
SELECT * FROM TASK_SPECS_CURRENT;       -- View läuft fehlerfrei → PASS
Alle drei müssen grün sein → GESAMTPASS
Sonst → FAIL + STOP
```

**Scope — macht NICHT:**
Keine weiteren Tabellen (`DEV_COMMENTS`, `TEST_RESULTS`), keine RAP, kein Multi-Tenant vollständig ausgebaut — das kommt in Phase 1.

---

## Abschluss Phase 0

Alle 6 Pakete PASS → **Phase 0 abgeschlossen.**

Claude Code erstellt einen Abschlussbericht mit:
- Status jedes Pakets (PASS/FAIL)
- Evidence (Outputs, Versionsnummern, SQL-Ergebnisse)
- Offene Punkte für Phase 1

Dieser Bericht wird als `phase0_report.md` gespeichert und in die PrepSmart Project Knowledge hochgeladen.

---

## Hilfsreferenzen (✏️ SEKUNDÄR — kritisch prüfen, nicht als Vorlage kopieren)

> **Deine Regel:** Primärquelle ist immer Snowflake/Anthropic offiziell. Das Folgende ist nur Orientierung, kein Spezifikations-Ersatz.

**Konzeptionelle Referenz — LangGraph + Cortex in SPCS:**
Prathamesh Nimkar, „Snowflake AI Agentic Workflows using LangChain and LangGraph" (Medium, Nov 2024) — https://medium.com/@prathamesh.nimkar/snowflake-agentic-workflows-160a6b83b688
Zeigt das Grundmuster: LangGraph-Routing + Cortex-Orchestrierung, optional gehostet in SPCS.

**⚠️ Zwei Fallen bei diesem und ähnlichen Tutorials:**
1. **Veraltet (Nov 2024):** Cortex-Modelle, SPCS-Details und Lizenzlage haben sich geändert. Nur als *Konzept* nutzen, **niemals** Code 1:1 übernehmen. Jeden Schritt gegen die offiziellen Snowflake-Docs verifizieren.
2. **Lizenz-Falle:** Viele LangGraph-Deployment-Tutorials deployen den **LangGraph-Server** (Docker + LangSmith Plus, kostenpflichtig, Elastic License 2.0). Das ist genau das, was wir NICHT tun. Wir nutzen ausschließlich die `langgraph`-**Library** (MIT) als In-Process-Code. Wenn ein Tutorial `langgraph deploy`, `langgraph build`, LangSmith-Account oder Studio-UI verlangt → falscher Pfad, ignorieren.

**Offizielle Primärquellen (verbindlich):**
- SPCS-Überblick — https://docs.snowflake.com/en/developer-guide/snowpark-container-services/overview
- SPCS Considerations (OAuth-Token / interner host) — https://docs.snowflake.com/en/developer-guide/snowpark-container-services/additional-considerations-services-jobs
- Cortex REST API — https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-rest-api
- LangGraph LICENSE (MIT) — https://github.com/langchain-ai/langgraph/blob/main/LICENSE
