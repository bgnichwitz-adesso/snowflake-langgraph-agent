# Sub-Spec · Lernfrequenz
### Teil von PrepSmart · Stand: 13. Juni 2026 · wiederverwendbar (Multi-User)

> **Zweck:** Definiert Takt und Dosis des Lernens. Pro Nutzer eine Instanz; steuert die tägliche Lerndauer-Frage, das Ziel-Feedback und die Reminder (Haupt-Spec §7).

## Generisches Schema (Felder)
| Feld | Beschreibung |
|---|---|
| `user_id` / `tenant_id` | Identität & Mandant |
| `daily_median_min` | tägliches Median-Lernziel (Min) |
| `daily_corridor_min` | erlaubter Korridor (min–max) |
| `weekly_target_min` | Wochen-Richtwert |
| `slots` | bevorzugte Lern-Slots |
| `weekly_test_day` | fixer Test-Tag |
| `reminder_mode` | Erinnerungs-Mechanismus |
| `goal_feedback` | aktives Feedback gegen Ziel (ja/nein) |

## Konkrete Instanz — aktueller Nutzer
- **daily_median_min:** ~30 (inkl. Sonntags-Test)
- **daily_corridor_min:** 10–45
- **weekly_target_min:** ~210
- **slots:** mobil morgens (leicht) · Laptop abends (tief)
- **weekly_test_day:** Sonntag
- **reminder_mode:** Variante D — Apple Kalender (Trigger) + Claude Project Ritual (Status beim Öffnen)
- **goal_feedback:** ja — tägliche Frage „Wie lange/wann?" + ehrliche Rückmeldung, ob mehr nötig ist, um die Ziele zu erreichen
