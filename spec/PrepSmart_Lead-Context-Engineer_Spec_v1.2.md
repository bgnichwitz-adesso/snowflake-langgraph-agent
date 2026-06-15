# PrepSmart — Lead Context Engineer Trainings- & Leadership-System
### Grundsatz-Spec v1.2 · Stand: 13. Juni 2026
### Änderungen ggü. v1.1: Produktisierung — Nutzer-Profil/Lernziele/Lernfrequenz als Sub-Specs ausgelagert · neues §4a (Mandantenfähigkeit, Anmeldung, Datenmodell mit Row Access Policies) · App wird Multi-Tenant/Multi-User
### Änderungen ggü. v1.0: §5/§6 auf offizielle Taxonomie umgestellt · neues §7 (Events & Kadenz) · neues §8 (Tägliche System-Routine) · variable Lerndauer · Korrektur: 30-Min-Median-Lernziel statt „3–5 Min" · neues §7.5 (gemeinsamer, dialogischer Aufbau der Kategorien)

> **Was dieses Dokument ist:** Grundsatzentscheidungen für ein tägliches Begleitsystem, das aus dem Nutzer den besten *Lead Context Engineer für Conversational Agents im Versicherungsbereich* macht. Bewusst auf Grundsatzebene — keine Implementierungsdetails. Einstiegspunkt jeder Folgesession; Grundlage für die Implementierung mit Claude Code.
>
> **Begleitende Dokumente:** `00_MASTER_Foundry-Evaluators_Hierarchie.md` (Taxonomie + Navigation) und die Sub-Dokumente je Evaluator (Template: `Sub_RAG_Groundedness_TEMPLATE.md`). **Nutzerspezifische Sub-Specs:** `subspec_user-profile.md`, `subspec_learning-goals.md`, `subspec_learning-frequency.md`.

---

## 1. Vision & Endzustand
Der Nutzer tritt sicher als Lead Context Engineer auf — fachlich (Azure AI Foundry & AWS Evaluation Frameworks) und in der Führung (Literal Leadership). Er behält im Projektalltag die Übersicht, lenkt Gespräche ins Ziel, hält das Team beim Bau des Conversational Agent auf Kurs.
**Zwei getrennt bewertete Erfolgsdimensionen:** (1) **Wissen**, (2) **Führung**.
**Format:** 7-Tage-Kickstart (intensiv) → dauerhafter täglicher Begleiter. **Kein Ablaufdatum.**

## 2. Profil des Lernenden
Nutzerspezifische Angaben sind **ausgelagert** (wiederverwendbar / Multi-User):
- `subspec_user-profile.md` — Rolle, Erfahrung, Start-Wissensstand, Geräte, Sprache, Zeitzone.
- `subspec_learning-goals.md` — übergeordnetes Ziel, Teilziele, Erfolgskriterien.
- `subspec_learning-frequency.md` — Median-Lernziel, Korridor, Slots, Test-Tag, Reminder.

Die konkrete Instanz des aktuellen Nutzers steht in diesen Sub-Specs, nicht hier — damit die Haupt-Spec generisch und für weitere Nutzer wiederverwendbar bleibt.

## 3. Glossar & Zielgruppen-Regel
**Regel für Claude:** Vor dem Formulieren immer klären, für welche Zielgruppe/Ebene. Im Zweifel fragen.

| Kontext / Zielgruppe | Begriff |
|---|---|
| IT/Microsoft-Background, extern, unbekannt | **Conversational Agent** |
| Lead/Management Vertreterbereich, extern, unbekannt | **Conversational Agent Advisor** |
| Intern (Team) | *Name vom PO — TBD* |

## 4. System-Architektur (3 Ebenen)
| Ebene | Was | Rolle |
|---|---|---|
| **1 — PrepSmart Project** | Living Context Document (Markdown): Glossar, Trainingslog, Scores, Ziele, Tagebuch. In Project Knowledge. | Single Source of Truth, Gedächtnis über Sessions. |
| **2 — Streamlit in Snowflake** | **Multi-User-App** mit Anmeldeprozess & User-Profil. Dashboard: Fortschritt, Scores, Historie. Ruft Claude über **Enterprise API Key**. | Visuelles Cockpit, wiederverwendbar durch viele Nutzer. Hosting komplett in Snowflake. |
| **3 — Handy (Claude App)** | Immer PrepSmart Project + Living Context Document. | Sessions zwischendurch. |

**Grundsatz:** Egal ob App/Handy/Desktop — Claude hat **immer den gesamten Kontext** (über das Living Context Document).
**Implementierung:** durch den Nutzer mit Claude Code, ab Abend 13.06.

## 4a. Mandantenfähigkeit, Anmeldung & Datenmodell (✏️ Produktisierung)
> Ziel: Die App ist **wiederverwendbar** und **multi-tenant-fähig** — viele Nutzer (perspektivisch mehrere Organisationen) nutzen sie gleichzeitig, strikt isoliert.

**Entscheidung — Tenant-Granularität (Variante C):** B-fähig bauen, A-einfach starten. Schema von Beginn an mit `TENANT_ID`, aber zunächst ein **Default-Tenant** (reine User-Isolation aktiv). Org-Verwaltung (mehrere Mandanten mit je vielen Nutzern) ist vorgesehen und später aktivierbar — ohne Schema-Migration.

**Anmeldung & Onboarding**
- Anmeldeprozess Pflicht; beim ersten Login **Onboarding**, das User-Profil, Lernziele und Lernfrequenz erfasst (befüllt die drei Sub-Specs pro Nutzer).
- Identität: Snowflake-Auth/SSO bevorzugt; alternativ App-eigene User-Verwaltung.

**Zwei Daten-Layer (Grundsatz)**
- **Content-Layer (global, wiederverwendbar):** Master-Hierarchie + die 36 Evaluator-Sub-Docs + Lerninhalte. Tenant-übergreifend, nicht nutzerspezifisch.
- **User-Data-Layer (isoliert):** Profil, Ziele, Frequenz, Trainingslog, Scores, Journal. Pro Nutzer/Tenant, RLS-geschützt.

**Datenmodell (Grundsatz-Tabellen)**
- `TENANTS` (tenant_id, …) · `USERS` (user_id, tenant_id, login, …)
- `USER_PROFILE` / `LEARNING_GOALS` / `LEARNING_FREQUENCY` (je user_id, tenant_id)
- `TRAINING_LOG`, `SCORES`, `JOURNAL` (je user_id, tenant_id)
- `EVALUATOR_CONTENT` (global, kein user_id)
- Jede User-Data-Tabelle trägt `TENANT_ID` **und** `USER_ID`.

**Isolation: Row Access Policies (Snowflake)**
- Row Access Policy auf den User-Data-Tabellen, gebunden an `TENANT_ID` (Mandanten-Isolation) **und** `USER_ID` (Nutzer sieht nur eigene Daten).
- Mapping eingeloggter App-User → `USER_ID`/`TENANT_ID` über Session-Kontext / Mapping-Tabelle; an alle Queries weiterreichen.
- Content-Layer bleibt global lesbar (keine RAP bzw. reine Lesefreigabe).

## 5. Das Bewertungs-Framework (Azure AI Foundry) — offizielle Taxonomie
**Korrektur ggü. v1.0:** Nicht „3 Kategorien", sondern die **offizielle 7er-Struktur**: General purpose · Textual similarity · RAG · Risk and safety · Agent · Azure OpenAI graders · Custom (preview). 36 Evaluatoren. Zweite Achse: **System** (Ergebnis) vs. **Process** (Weg).
→ Vollständige Hierarchie, Originalbegriffe, Quell-Links und Sub-Doc-Navigation im **Master-Dokument** `00_MASTER_…`. Projekt-Priorisierung und Cost/Latency dort als ✏️ (kein Framework-Bestandteil) markiert.

## 6. Bewertungssystem — der Sonntags-Test
**Slot:** jeden **Sonntag** (Laptop, ~30 Min). Fest.
**Bewertet in zwei Säulen:**
- **Wissen** — entlang der offiziellen Gruppen/Evaluatoren (§5 / Master-Doc). Beginnend mit dem RAG+Agent+Safety-Kern.
- **Führung** — Literal Leadership (§9).
**Mechanik:** Claude nennt nach jedem Test den gesetzten methodischen **Schwerpunkt**, fragt die **Selbsteinschätzung** ab und bewertet dann objektiv aus der Außenperspektive — auf Basis der Testergebnisse **und** der gesamten Interaktion. Ergebnis: wöchentliches Kompetenzprofil (Score je Gruppe + Führung) → Dashboard + Living Context Document.

## 7. Events & Kadenz (dediziertes Kapitel)
> Alle wiederkehrenden Termine zentral. Variable Lerndauer ist Pflicht — das System passt sich dem Alltag an.

### 7.1 Lerndauer-Maxime (✏️ Projektregel)
- **Tägliches Median-Lernziel: ~30 Min/Tag**, inklusive des Sonntags-Tests (der ~30 Min dauert).
- **Lerndauer wird variiert**; Korridor ca. 10–45 Min/Tag, je nach Tag.
- Wochen-Richtwert ≈ 7 × 30 = **~210 Min**.
- **Ziel-Feedback (Pflicht):** Das System gibt aktiv Rückmeldung, **ob der Nutzer mehr lernen sollte, um seine Ziele zu erreichen** — nicht nur einen Dauer-Vorschlag, sondern eine ehrliche Einordnung gegen Wochen-Richtwert und Lernziel.

### 7.2 Tägliche Lerndauer-Frage (Pflicht beim Session-Start)
Claude fragt **jeden Tag**: *„Wie lange und wann willst du heute lernen?"* — und gibt **vorher eine Empfehlung**, basierend auf:
- dem Lernziel (Kickstart vs. Dauerbetrieb),
- der in der **laufenden Woche bereits investierten Zeit** (Rest-Budget / verbleibende Tage),
- dem Tagestyp (mobil/Zug = kürzer & leicht; Laptop-Abend = länger & tief).

Die Empfehlung enthält immer das **Ziel-Feedback** (§7.1): liegt der Nutzer im Plan, oder sollte er heute/diese Woche mehr lernen, um seine Ziele zu erreichen?

### 7.3 Event-Übersicht
| Event | Kadenz | Dauer | Inhalt | Ziel |
|---|---|---|---|---|
| **Session-Start / Check-in** | täglich, bei jedem Öffnen | kurz (~1 Min) | Status + nächster Schritt + Lerndauer-Frage (§7.2) | Orientierung, Alltags-Anpassung |
| **Micro-Learning** | 1–2× täglich | Hauptteil des Tagesbudgets | 1 Evaluator/Konzept als *was/wo/wie/warum* + Szenario + Feedback; Methodik adaptiv variiert; Sub-Docs entstehen dabei **gemeinsam** (§7.5) | Wissensaufbau, gemessen |
| **Daily Journal & Ziele** | täglich | kurzer Teil des Tagesbudgets | morgens Ziele, abends Reflexion (Literal-Leadership-Fragen §9) | Führungsentwicklung |
| **Weekly Test** | Sonntag | ~30 Min (= Tagesbudget am Sonntag) | Wissen (offizielle Gruppen) + Führung; Selbst- vs. Fremdbild | Kompetenzprofil, Standortbestimmung |

> **Kein Widerspruch zur 30-Min-Maxime:** Die Event-Dauern sind keine Zusatzzeiten, sondern die **Aufteilung** des für den Tag gewählten Budgets (Median ~30 Min). Es gibt **kein** „nur 3–5 Min lernen" — das war ein Fehler in früheren Entwürfen und ist hiermit korrigiert.

### 7.4 Reminder/Ping (Variante „D")
- **Apple Kalender** triggert Sessions: mobil morgens + Laptop abends (genaue Zeiten TBD).
- **Claude Project Ritual:** beim Öffnen sofort Status + nächster Schritt (Living Context Document zuerst lesen).
- Fortschritts-Pings über Dashboard (Ebene 2) + Ritual.

### 7.5 Aufbau der Kategorien — gemeinsam & dialogisch (✏️ Grundsatz)
Die Sub-Dokumente werden **nicht** vorab als Massenproduktion erzeugt, sondern **gemeinsam im Training** erarbeitet — jede Micro-Learning-Einheit baut eine Kategorie auf. Die offiziellen Quellen liefern dabei **keine kalten Antworten**: Claude erklärt dialogisch, knüpft an die konkreten Fragen des Nutzers an und verankert das Wissen, statt Doku-Text zu kopieren. Ergebnis jeder Einheit ist das fertige, vom Nutzer mitgestaltete Sub-Doc.

## 8. Tägliche System-Routine (Quellen- & Aktualitätspflege)
> Eigene Routine des Systems, damit Inhalte nie veralten. Primärquelle bleibt **immer Microsoft & AWS offiziell**.

**Täglich auszuführen (durch Claude/System):**
1. **Link-Check:** jeden Quell-Link in allen Kern-Dokumenten prüfen — erreichbar? Inhalt aktualisiert (MS-Stand-Datum geändert)?
2. **Inhalts-Update:** bei nachgewiesenen Framework-Änderungen die betroffenen Kern-Dokumente aktualisieren; Änderung im Quellen-Block (Datum) vermerken.
3. **Artikel-Sichtung:** aktuelle Artikel zu beiden Frameworks **kritisch** bewerten — niemals als Primärquelle übernehmen; nur als Hinweis, der gegen die offizielle MS/AWS-Doku verifiziert wird.
4. **Protokoll:** Ergebnis (geprüft/geändert/keine Änderung) im Living Context Document festhalten.

**Quellen-/Markierungs-Konvention (gilt überall):** 📘 = Framework (offiziell, mit Link) · ✏️ = Ergänzung von uns · Originalbegriffe englisch & unverändert · jedes Dokument trägt einen Quellen-Block.

## 9. Leadership-Coaching — „Literal Leadership"
**Definition (Nutzer):** Führung auf Basis absoluter Klarheit, Transparenz, Authentizität; Botschaften ohne doppelten Boden — **aber** mit korrektem Timing: *wie* und *wann* zählt genauso.
**Tägliches Ritual:** Ziele + Tagebuch; Claude bewertet Wissen **und** Führung.
**Reflexionsfragen:** War es der richtige Zeitpunkt? Die richtige Gruppe/Person? Maximal ehrlich & transparent? Wie habe ich es gesagt — landete es ohne doppelten Boden?
**Grundlagen (zu bestätigen):** *Radical Candor* (Scott) · *Crucial Conversations* (Patterson et al.) · *Thanks for the Feedback* (Stone & Heen).

## 10. 7-Tage-Kickstart (thematische Grobgliederung, nur Microsoft)
| Tag | Wissens-Fokus | Führungs-Fokus |
|---|---|---|
| 1 | Warum Agent-Evaluation? Offizielle 7er-Taxonomie + System/Process | Tagebuch-Routine etablieren |
| 2 | RAG: Groundedness, Relevance, Retrieval | Klarheit: Botschaft präzise formulieren |
| 3 | Risk & Safety (Gruppe 4), Bezug regulierte Branche | Timing: wann eine Botschaft landet |
| 4 | Agent/System: Intent Resolution, Task Adherence, Task Completion | richtige Zielgruppe wählen |
| 5 | Agent/Process: Tool Call Accuracy & Co. | Schwieriges ehrlich + transparent ansprechen |
| 6 | Zusammenspiel im Snowflake-Kontext (Conversational Agent) | Gespräch ins Ziel lenken, Team auf Kurs |
| 7 (So) | **Erster Sonntags-Test** + Kompetenzprofil | Wochenreflexion; Ziele Woche 2 |

## 11. Dauerbetrieb (nach Kickstart)
Täglicher Begleiter ohne Ende; System wächst mit. Sonntags-Test bleibt Taktgeber. Methodik wird adaptiv variiert und gemessen.

## 12. AWS-Phase (nach Kickstart)
Start **nach** dem Kickstart. Danach **durchgängig vergleichend**: Pro/Contra, Fokus auf die Unterschiede zu Microsoft — und *warum* sie so entschieden haben (Führungsebene). Primärquelle: AWS offiziell.

## 13. Tracking-Dimensionen
Datum, Slot (mobil/Laptop), Dauer (geplant vs. real), Thema, gesetzter methodischer Schwerpunkt, Selbst- vs. Fremdbewertung, Score je offizieller Gruppe (Wissen) + Führungs-Score, Tagesziele & Reflexion, Beobachtungen aus *allen* Interaktionen, Ergebnis der täglichen System-Routine.

## 14. Offene Entscheidungen für die nächste Session
1. Interner Agent-Name (PO).
2. Konkrete Kalenderzeiten (morgens mobil / abends Laptop).
3. Bestätigung/Anpassung Leadership-Bücher.
4. Freigabe des Sub-Doc-Templates → **gemeinsamer** Aufbau der 36 Evaluatoren im Training (§7.5), nicht als Massenproduktion.
5. Datenmodell des Living Context Document.
6. Streamlit-in-Snowflake-Architektur (mit Claude Code).
7. AWS-Framework: konkrete offizielle Quellen festlegen.
8. ~~Tenant-Granularität~~ → **entschieden: Variante C** (B-fähig bauen, mit Default-Tenant A-einfach starten).
9. **Auth-Methode:** Snowflake-SSO vs. App-eigene User-Verwaltung.
