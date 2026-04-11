# Versioning — StatusPage Monitor

> Verplaatst vanuit `CLAUDE.md` op 2026-04-11. CLAUDE.md verwijst naar dit bestand.

Versie staat in `manifest.json`. Formaat: `[jaar].[maand].[release]`.

- `[jaar].[maand]` = het jaar en de maand van de release (bijv. `2026.3`)
- `[release]` = oplopend getal binnen die maand: `1`, `2`, `3` …
- Hotfixes krijgen gewoon het volgende oplopende nummer (geen letter-suffixen — HA's `AwesomeVersion` parser accepteert die niet in `manifest.json`)

| Situatie | Versie |
|---|---|
| Eerste release in maart 2026 | `2026.3.1` |
| Hotfix op die release | `2026.3.2` |
| Tweede feature-release in maart 2026 | `2026.3.3` |
| Eerste release in april 2026 | `2026.4.1` |

Update `manifest.json` automatisch als onderdeel van elke PR.
