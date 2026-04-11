# StatusPage Monitor – Claude context

## Project

Home Assistant custom integration that monitors status pages and exposes health data as sensors.

- Integration domain: `statuspage_monitor`
- Installed at: `/config/custom_components/statuspage_monitor/` on the HA instance
- Repo root: `custom_components/statuspage_monitor/`

## HA Iron Law

- ALTIJD async/await gebruiken
- Timestamps via dt_util, nooit datetime.now()
- Entiteit-attributen altijd JSON-serializable
- DataUpdateCoordinator pattern voor polling

## Git workflow

- Main branch: `statuspage-monitor-main`

## Referentiebestanden

Gedetailleerde info staat in aparte bestanden:

| Bestand | Inhoud |
|---|---|
| [`docs/claude-architecture.md`](docs/claude-architecture.md) | File structure, sensor entities, HA entity conventions, data model |
| [`docs/claude-providers.md`](docs/claude-providers.md) | Provider interface, volgorde, nieuwe provider toevoegen, toekomstige providers research |
| [`docs/claude-pitfalls.md`](docs/claude-pitfalls.md) | Known pitfalls + bekende kleine tekortkomingen uit codebase review |
| [`docs/claude-versioning.md`](docs/claude-versioning.md) | Versie-formaat voor `manifest.json` |
| [`docs/baserow-rest-api-reference.md`](docs/baserow-rest-api-reference.md) | Baserow REST API templates (gedeeld bestand — zie waarschuwing in bestand zelf) |
