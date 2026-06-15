# Groundedness · RAG evaluator (System evaluation)
### Sub-Dokument · Priorität: ✏️ HOCH · Status: 🟦 Template/Muster

> Aufbau jedes Sub-Dokuments: **WAS → MESSPUNKT (was/wo) → WIE → WARUM → Beispiel → Abgrenzung → Selbstcheck → Quellen.**

---

## 📘 WAS (offizielle Definition)
**Groundedness** misst, wie gut die generierte Antwort mit dem bereitgestellten Kontext übereinstimmt, **ohne Inhalte zu fabrizieren**. Es ist der **Precision-Aspekt** der Antwort: Die Antwort enthält nichts, was nicht durch den Grounding-Kontext gedeckt ist.
Gehört zur **System evaluation** (bewertet das Ergebnis, nicht den Retrieval-Weg).
📘 [RAG evaluators — Microsoft Learn](https://learn.microsoft.com/en-us/azure/foundry/concepts/evaluation-evaluators/rag-evaluators)

## 📘 MESSPUNKT — was wird wo gemessen?
- **Gemessene Komponente:** die generierte **`response`** (finale Antwort des Agenten).
- **Bezugsgröße (gegen was):** der **`context`** — die im Retrieval gefundenen Grounding-Dokumente.
- **Optional:** **`query`** verbessert das Scoring.
- **Ort im Agent-Flow:** **nach** der Antwortgenerierung, auf der **System-Ebene** (Output) — unabhängig vom Retrieval-Schritt selbst (den misst *Retrieval* / *Document Retrieval*).

## 📘 WIE (Messung)
- **Required inputs:** `response`, `context` (empfohlen); `query` optional für besseres Scoring; oder `query`+`response` im Agent-Response-Modus.
- **Required parameter:** `deployment_name` (eigenes GPT-Modell als LLM-Judge — „bring your own").
- **Output:** Score **1–5** (1 = sehr schwach, 5 = exzellent), **Default-Threshold = 3**. Ergebnis ab Threshold = `pass`. Rückgabe binär Pass/Fail plus `reason`.
- **Beispiel-Output (📘 offiziell):** Felder `score`, `label`, `reason`, `threshold`, `passed`.

## ✏️ WARUM (für unseren Versicherungs-Agenten)
Im Versicherungskontext ist eine erfundene Aussage (z.B. eine nicht existierende Klausel oder Deckungssumme) ein **direktes Compliance- und Haftungsrisiko**. Groundedness ist die Metrik, die genau das abfängt: Der *Conversational Agent Advisor* darf nur sagen, was die Quelldokumente hergeben. Deshalb HOCH priorisiert.

## ✏️ Beispiel
- **Kontext:** „Die Hausratversicherung deckt Schäden durch Leitungswasser bis 50.000 €."
- **Gute Antwort (grounded, Score ~5):** „Leitungswasserschäden sind bis 50.000 € gedeckt."
- **Schlechte Antwort (ungrounded, Score ~2):** „Leitungswasserschäden sind bis 50.000 € gedeckt, inklusive Hochwasser." → *Hochwasser* steht nicht im Kontext = Fabrikation.
- **Gemessen wird:** die *response* gegen den *context*. Der Score fällt, weil die Komponente „Hochwasser" in der Antwort **keine Deckung** im Kontext hat.

## ✏️ Abgrenzung
- **vs. Response Completeness:** Groundedness = *Precision* (nichts Erfundenes). Response Completeness = *Recall* (nichts Wichtiges fehlt). 📘 Beide Begriffe definiert Microsoft als Gegenstückpaar.
- **vs. Groundedness Pro:** Pro nutzt den Azure-AI-Content-Safety-Dienst und gibt True/False statt 1–5 zurück.
- **vs. Retrieval:** Retrieval bewertet den *Weg* (Kontextqualität), Groundedness das *Ergebnis*.

## 🧠 Selbstcheck (10-Sek-Micro-Learning)
1. Precision oder Recall — was misst Groundedness? *(→ Precision)*
2. Welche zwei Inputs sind empfohlen? *(→ response, context)*
3. Default-Threshold? *(→ 3 von 5)*

---

## Quellen-Block (täglich zu prüfen)
| Quelle | Link | Zuletzt geprüft | MS-Stand |
|---|---|---|---|
| RAG evaluators | https://learn.microsoft.com/en-us/azure/foundry/concepts/evaluation-evaluators/rag-evaluators | 13.06.2026 | 04.04.2026 |
| Built-in evaluators reference | https://learn.microsoft.com/en-us/azure/foundry/concepts/built-in-evaluators | 13.06.2026 | 07.03.2026 |
| Groundedness SDK-Sample | https://github.com/Azure/azure-sdk-for-python/blob/main/sdk/ai/azure-ai-projects/samples/evaluations/agentic_evaluators/sample_groundedness.py | 13.06.2026 | — |
