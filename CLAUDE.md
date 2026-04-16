# StatusPage Monitor – Claude context

## Shared Knowledge

Deze repo maakt gebruik van een gedeelde knowledge base in
`~/Documents/Apps/shared-knowledge/`. Voor universele kennis raadpleeg:

- **Project metadata**: [`../shared-knowledge/project-registry.yaml`](../shared-knowledge/project-registry.yaml) entry `statuspage-ha`
- **Baserow**: [`rest-api-reference`](../shared-knowledge/baserow/rest-api-reference.md) · [`conventions`](../shared-knowledge/baserow/conventions.md) · [`schema-changelog`](../shared-knowledge/baserow/schema-changelog.md)
- **Backend**: [`home-assistant`](../shared-knowledge/backend/home-assistant.md)
- **Workflow**: [`git`](../shared-knowledge/workflow/git.md) · [`karpathy-skills`](../shared-knowledge/workflow/karpathy-skills.md)

Onderstaande secties beschrijven **uitsluitend projectspecifieke** regels die
afwijken van of aanvullen op de shared-knowledge baseline.

---

## Project

Home Assistant custom integration that monitors status pages and exposes
health data as sensors.

- Integration domain: `statuspage_monitor`
- Installed at: `/config/custom_components/statuspage_monitor/` on the HA instance
- Repo root: `custom_components/statuspage_monitor/`
- Release channel: HACS (Home Assistant Community Store)

## HA Iron Law

- ALTIJD async/await gebruiken
- Timestamps via dt_util, nooit datetime.now()
- Entiteit-attributen altijd JSON-serializable
- DataUpdateCoordinator pattern voor polling

## Git workflow — projectspecifiek

- Main branch: **`statuspage-monitor-main`** (niet `main`)

## Referentiebestanden (project-lokaal)

| Bestand | Inhoud |
|---|---|
| [`docs/claude-architecture.md`](docs/claude-architecture.md) | File structure, sensor entities, HA entity conventions, data model |
| [`docs/claude-providers.md`](docs/claude-providers.md) | Provider interface, volgorde, nieuwe provider toevoegen, toekomstige providers research |
| [`docs/claude-pitfalls.md`](docs/claude-pitfalls.md) | Known pitfalls + bekende kleine tekortkomingen uit codebase review |
| [`docs/claude-versioning.md`](docs/claude-versioning.md) | Versie-formaat voor `manifest.json` |

---

## Shared-knowledge actualiteit

Wijzigingen aan `../shared-knowledge/` raken automatisch dit project —
raadpleeg altijd de shared files eerst voor cross-project vragen (Baserow,
Home Assistant patterns, git).
