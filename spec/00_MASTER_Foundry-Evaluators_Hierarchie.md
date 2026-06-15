# 00 · MASTER — Azure AI Foundry Evaluators · Hierarchie
### Zentrale Übersicht & Navigationskarte · Stand: 13. Juni 2026

> **Rolle dieses Dokuments:** Das Rückgrat der Lernstruktur. Es bildet die **offizielle** Microsoft-Taxonomie 1:1 ab und verlinkt auf je ein Mini-Dokument pro Evaluator (Aufbau dort: *was / wo gemessen / wie / warum / Beispiel / Abgrenzung / Selbstcheck*).

---

## Konventionen (gelten in ALLEN Dokumenten)

- **📘 FRAMEWORK** — Inhalt stammt direkt aus offizieller Microsoft-/AWS-Quelle. Immer mit Quell-Link.
- **✏️ ERGÄNZUNG** — Inhalt von uns hinzugefügt (didaktisch, Beispiel, Versicherungs-Bezug, Projekt-Priorisierung). Nicht Teil des Frameworks.
- **Originalbegriffe bleiben englisch und unverändert.** Übersetzungen stehen nur als ✏️-Hilfe daneben.
- **Quellenpflicht:** Jedes Dokument trägt unten seinen Quellen-Block mit Links + Datum „zuletzt geprüft". Prüfung täglich (siehe Spec-Kapitel „Tägliche System-Routine").

---

## 📘 Die offizielle Taxonomie — 7 Gruppen

> ⚠️ **Wichtige Klarstellung (✏️):** Die in vielen Blogs verbreitete Dreiteilung „Quality / Safety / Agent" ist eine **Vereinfachung**. Die offizielle *Built-in evaluators reference* gliedert in **sieben Gruppen**. Wir folgen der offiziellen Struktur.

| # | Gruppe (Originalname) | Anzahl | Für unseren RAG-Versicherungs-Agenten |
|---|---|---|---|
| 1 | **General purpose evaluators** | 2 | ✅ |
| 2 | **Textual similarity evaluators** | 6 | teilweise (Similarity) |
| 3 | **RAG evaluators** | 6 | ✅ Kern |
| 4 | **Risk and safety evaluators** | 9 | ✅ (regulierte Branche) |
| 5 | **Agent evaluators** | 9 | ✅ Kern |
| 6 | **Azure OpenAI graders** | 4 | optional |
| 7 | **Custom evaluators (preview)** | — | später |
| | **Summe** | **36** | |

📘 Quelle: [Built-in evaluators reference — Microsoft Learn](https://learn.microsoft.com/en-us/azure/foundry/concepts/built-in-evaluators)

---

## 📘 Quer-Struktur: System- vs. Process-Evaluation

Microsoft unterscheidet bei RAG **und** Agent zwei Blickwinkel — das ist eine zweite, sehr nützliche Achse:

- **System evaluation** = Qualität des **Ergebnisses** (das *OB*). Bei RAG: Groundedness, Relevance, Response Completeness. Bei Agent: Task Completion, Task Adherence, Intent Resolution, Task Navigation Efficiency.
- **Process evaluation** = Qualität des **Wegs** (das *WIE*). Bei RAG: Retrieval, Document Retrieval. Bei Agent: alle Tool-Evaluatoren.

📘 Quelle: [RAG evaluators — Microsoft Learn](https://learn.microsoft.com/en-us/azure/foundry/concepts/evaluation-evaluators/rag-evaluators) · [Agent evaluators — Microsoft Learn](https://learn.microsoft.com/en-us/azure/foundry/concepts/evaluation-evaluators/agent-evaluators)

---

## 📘 Alle 36 Evaluatoren + Sub-Dokument-Navigation

Status: ⬜ offen · 🟦 Template · ✅ fertig. *(Sub-Docs werden nach Freigabe des Templates ausgerollt.)*

### Gruppe 1 — General purpose · [Quelle](https://learn.microsoft.com/en-us/azure/foundry/concepts/evaluation-evaluators/general-purpose-evaluators)
| Evaluator | 📘 Purpose (offiziell, paraphrasiert) | Sub-Doc |
|---|---|---|
| Coherence | logische Konsistenz und Fluss der Antwort | ⬜ |
| Fluency | natürliche Sprachqualität / Lesbarkeit | ⬜ |

### Gruppe 2 — Textual similarity · [Quelle](https://learn.microsoft.com/en-us/azure/foundry/concepts/evaluation-evaluators/textual-similarity-evaluators)
| Evaluator | 📘 Purpose | Sub-Doc |
|---|---|---|
| Similarity | KI-gestützte Textähnlichkeit | ⬜ |
| F1 Score | harmonisches Mittel aus Precision/Recall über Token-Overlap vs. Ground Truth | ⬜ |
| BLEU | Übersetzungsqualität über n-gram-Overlap | ⬜ |
| GLEU | Google-BLEU-Variante, Satz-Ebene | ⬜ |
| ROUGE | Recall-orientierter n-gram-Overlap | ⬜ |
| METEOR | n-gram-Overlap mit expliziter Reihenfolge | ⬜ |

### Gruppe 3 — RAG · [Quelle](https://learn.microsoft.com/en-us/azure/foundry/concepts/evaluation-evaluators/rag-evaluators)
| Evaluator | System/Process | 📘 Purpose | Sub-Doc |
|---|---|---|---|
| Retrieval | Process | Relevanz der abgerufenen Kontext-Chunks (LLM-Judge, ohne Ground Truth) | ⬜ |
| Document Retrieval | Process | Suchqualität vs. Ground-Truth-Labels (Fidelity, NDCG, XDCG, Max Relevance, Holes) | ⬜ |
| **Groundedness** | System | Deckung der Antwort durch den Kontext, ohne Fabrikation (Precision) | 🟦 **Template** |
| Groundedness Pro (preview) | System | strenge Konsistenz via Azure AI Content Safety | ⬜ |
| Relevance | System | Genauigkeit/Vollständigkeit/Direktheit der Antwort zur Query | ⬜ |
| Response Completeness (preview) | System | Vollständigkeit der Antwort vs. Ground Truth (Recall) | ⬜ |

### Gruppe 4 — Risk and safety · [Quelle](https://learn.microsoft.com/en-us/azure/foundry/concepts/evaluation-evaluators/risk-safety-evaluators)
| Evaluator | 📘 Purpose | Sub-Doc |
|---|---|---|
| Hate and Unfairness | erkennt voreingenommene/diskriminierende/hasserfüllte Inhalte | ⬜ |
| Sexual | erkennt unangemessene sexuelle Inhalte | ⬜ |
| Violence | erkennt Gewalt / Aufstachelung | ⬜ |
| Self-Harm | erkennt Inhalte zu Selbstverletzung | ⬜ |
| Protected Materials | erkennt unautorisierte Nutzung geschützter Inhalte | ⬜ |
| Code Vulnerability | erkennt Sicherheitslücken in generiertem Code | ⬜ |
| Ungrounded Attributes | erkennt fabrizierte/halluzinierte Attribute aus Nutzerinteraktion | ⬜ |
| Prohibited Actions (preview) | misst Verstöße gegen explizit verbotene Aktionen | ⬜ |
| Sensitive Data Leakage (preview) | misst Anfälligkeit für Offenlegung sensibler Daten | ⬜ |

### Gruppe 5 — Agent · [Quelle](https://learn.microsoft.com/en-us/azure/foundry/concepts/evaluation-evaluators/agent-evaluators)
| Evaluator | System/Process | 📘 Purpose | Sub-Doc |
|---|---|---|---|
| Task Adherence (preview) | System | folgt der Agent den Aufgaben gemäß System-Instruktionen? | ⬜ |
| Task Completion (preview) | System | wurde die Aufgabe end-to-end erfolgreich gelöst? | ⬜ |
| Intent Resolution (preview) | System | erkennt/adressiert der Agent die Nutzer-Absicht korrekt? | ⬜ |
| Task Navigation Efficiency | System | entspricht die Schrittfolge dem optimalen/erwarteten Pfad? | ⬜ |
| Tool Call Accuracy | Process | Gesamtqualität der Tool-Calls (Auswahl, Parameter, Effizienz) | ⬜ |
| Tool Selection | Process | wurden die passendsten/effizientesten Tools gewählt? | ⬜ |
| Tool Input Accuracy | Process | sind alle Tool-Parameter korrekt (Grounding, Typ, Format, …)? | ⬜ |
| Tool Output Utilization | Process | werden Tool-Ergebnisse korrekt kontextuell genutzt? | ⬜ |
| Tool Call Success | Process | liefen alle Tool-Calls technisch fehlerfrei? | ⬜ |

### Gruppe 6 — Azure OpenAI graders · [Quelle](https://learn.microsoft.com/en-us/azure/foundry/concepts/evaluation-evaluators/azure-openai-graders)
| Evaluator | 📘 Purpose | Sub-Doc |
|---|---|---|
| Model Labeler | klassifiziert Inhalte nach eigenen Richtlinien/Labels | ⬜ |
| String Checker | flexible Textvalidierung / Pattern-Matching | ⬜ |
| Text Similarity | Textqualität / semantische Nähe | ⬜ |
| Model Scorer | numerische Scores nach eigenen Richtlinien | ⬜ |

### Gruppe 7 — Custom evaluators (preview) · [Quelle](https://learn.microsoft.com/en-us/azure/foundry/concepts/evaluation-evaluators/custom-evaluators)
Selbst definierte Scoring-Logik. Eigenes Dokument folgt, sobald wir eigene Kriterien definieren.

---

## ✏️ Achse 2 — Projekt-Priorisierung (NICHT Framework)

> Diese Gewichtung ist **unsere** Use-Case-Entscheidung für den Versicherungs-RAG-Agenten, kein offizielles Microsoft-Ranking. Daher ✏️.

- **Hoch:** Relevance · Groundedness · Task Completion · Safety (gesamte Gruppe 4)
- **Mittel-Hoch:** Tool Call Accuracy
- **Mittel:** Fluency · Cost · Latency

## ✏️ Operational/Performance: Cost & Latency

> **Wichtig:** Cost und Latency sind **keine** Built-in Evaluators. Sie sind Betriebs-/Observability-Metriken (Azure Monitor / OTEL-Tracing). Wir führen sie getrennt, um nicht vom Framework abzuweichen.
📘 Kontext: [Observability in generative AI — Microsoft Learn](https://learn.microsoft.com/en-us/azure/foundry/concepts/observability)

## 📘 Microsofts offizielle Evaluator-Kombinationen
- **RAG-Anwendungen:** Retrieval + Groundedness + Relevance + Content Safety
- **Agent-Anwendungen:** Tool Call Accuracy + Task Adherence + Intent Resolution + Content Safety
- **Alle Anwendungen:** zusätzlich Risk-&-Safety-Evaluatoren für Responsible AI
📘 Quelle: [Built-in evaluators reference — Microsoft Learn](https://learn.microsoft.com/en-us/azure/foundry/concepts/built-in-evaluators)

---

## Quellen-Block (täglich zu prüfen)
| Quelle | Link | Zuletzt geprüft | MS-Stand |
|---|---|---|---|
| Built-in evaluators reference | https://learn.microsoft.com/en-us/azure/foundry/concepts/built-in-evaluators | 13.06.2026 | 07.03.2026 |
| RAG evaluators | https://learn.microsoft.com/en-us/azure/foundry/concepts/evaluation-evaluators/rag-evaluators | 13.06.2026 | 04.04.2026 |
| Observability | https://learn.microsoft.com/en-us/azure/foundry/concepts/observability | 13.06.2026 | — |
