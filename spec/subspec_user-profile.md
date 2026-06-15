# Sub-Spec · User-Profil
### Teil von PrepSmart · Stand: 13. Juni 2026 · wiederverwendbar (Multi-User)

> **Zweck:** Trennt die nutzerspezifischen Daten von der generischen Haupt-Spec. Pro Nutzer eine Instanz, beim Onboarding erfasst, im User-Data-Layer gespeichert (RLS-isoliert, siehe Haupt-Spec §4a).

## Generisches Schema (Felder)
| Feld | Beschreibung |
|---|---|
| `user_id` / `tenant_id` | Identität & Mandant (Isolation) |
| `display_name` | Anzeigename |
| `role` | aktuelle Rolle |
| `experience` | relevante Berufserfahrung |
| `domain` | Fachgebiet / Branche |
| `baseline_knowledge` | Start-Wissensstand je Framework |
| `preferred_method` | bevorzugte Lernmethode |
| `devices` | genutzte Geräte / Slots |
| `language` | Sprache |
| `timezone` | Zeitzone (für Reminder) |

## Konkrete Instanz — aktueller Nutzer
- **role:** Lead Context Engineer (Conversational Agents, Versicherung)
- **experience:** 15 J. Datenarchitekt (Snowflake), davon 10 J. Analytics Lead
- **domain:** Snowflake / Analytics / Versicherung
- **baseline_knowledge:** Azure AI Foundry Evaluation = **Null**; AWS = offen
- **preferred_method:** Mix (Erklärung → Szenario → Feedback), adaptiv variiert & gemessen
- **devices:** Handy (mobil/Zug, zwischendurch) + Laptop (abends, tief)
- **language:** Deutsch
- **timezone:** TBD (für Kalender-Reminder)
