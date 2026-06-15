# PrepSmart — Dokumentation

Grundsatz-Dokumente für den Lead-Context-Engineer-Lernbegleiter und den Agenten-Bau.
Alle Dokumente bleiben auf Grundsatzebene. Markierung durchgängig: **📘** = offizielle Quelle (verlinkt) · **✏️** = eigene Projektentscheidung.

## Lesereihenfolge

| # | Datei | Inhalt |
|---|---|---|
| 1 | `PrepSmart_Lead-Context-Engineer_Spec_v1.2.md` | Haupt-Spec: Vision, Architektur, Mandantenfähigkeit/RLS, Events & Lerndauer, Bewertung, Leadership, tägliche System-Routine |
| 2 | `00_MASTER_Foundry-Evaluators_Hierarchie.md` | Offizielle 7er-Taxonomie der Azure AI Foundry Evaluatoren, alle 36 verlinkt |
| 3 | `Sub_RAG_Groundedness_TEMPLATE.md` | Muster-Sub-Dokument je Evaluator (was/wo/wie/warum) |
| 4 | `subspec_user-profile.md` | Nutzerspezifisch: Profil |
| 5 | `subspec_learning-goals.md` | Nutzerspezifisch: Lernziele |
| 6 | `subspec_learning-frequency.md` | Nutzerspezifisch: Lernfrequenz |
| 7 | `Agent-Dev-Prinzipien_Deterministischer-Orchestrator.md` | Architektur: deterministischer Orchestrator, Test-Gate, Claude-als-Worker über Cortex, SPCS, RBAC/Append-Only |
| 8 | `Phase0_Bootstrap_Tasks.md` | **Heute Abend:** 6 Bootstrap-Pakete für Claude Code, jeder mit hartem Test-Gate |

## Start heute Abend
→ `Phase0_Bootstrap_Tasks.md`, Paket 1. Globale Regel: kein nächstes Paket ohne grünen Test + Evidence. Sauberer Stopp-Punkt nach Paket 3.

Stand: 13. Juni 2026
