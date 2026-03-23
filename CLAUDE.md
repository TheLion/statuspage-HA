# StatusPage Monitor – Claude context

## Project
Home Assistant custom integration that monitors status pages and exposes health data as sensors.
- Integration domain: `statuspage_monitor`
- Installed at: `/config/custom_components/statuspage_monitor/` on the HA instance
- Repo root: `custom_components/statuspage_monitor/`

## File structure
```
custom_components/statuspage_monitor/
├── __init__.py          # Integration setup, entity ID migration
├── const.py             # All constants (DOMAIN, provider IDs, status values, icons, colours)
├── coordinator.py       # DataUpdateCoordinator
├── config_flow.py       # UI config flow + options flow
├── sensor.py            # All sensor entities
└── providers/
    ├── __init__.py      # get_provider(), StatusPageData, Component dataclasses
    ├── base.py          # BaseProvider ABC
    ├── statuspage_io.py
    ├── status_io.py
    ├── instatus.py
    ├── sorry.py
    ├── uptimerobot.py
    ├── cachet.py
    └── logos/           # SVG provider logos (loaded as base64 data URLs)
```

## Sensor entities (per configured status page)
| Class | Entity ID suffix | Notes |
|---|---|---|
| `ProviderInfoSensor` | `_provider_info` | State = short provider name |
| `OverallStatusSensor` | `_overall_status` | ENUM: none/minor/major/critical |
| `ActiveIncidentsSensor` | `_active_incidents` | Count with incident list as attribute |
| `ActiveIncidentBodySensor` | `_active_incident_description` | Only if `SUPPORTS_INCIDENT_BODY = True` |
| `ScheduledMaintenanceSensor` | `_scheduled_maintenances` | Count with maintenance list |
| `ComponentSensor` | `_<component_slug>` | One per component, added dynamically |

All entity IDs follow the pattern `sensor.statuspage_<page_slug>_<suffix>`.

## HA entity attribute conventions
- Use `self._attr_*` to set entity attributes (NOT `self.<property_name>` directly).
  - `suggested_object_id` → `self._attr_suggested_object_id` (read-only property, no setter)
  - `unique_id` → `self._attr_unique_id`
  - `has_entity_name` → `self._attr_has_entity_name`
- Entity descriptions go in `entity_description` class attribute (not instance).

## Providers
Each provider class in `providers/` must implement:
- `ID: str` – matches constant in `const.py`
- `NAME: str` – full display name
- `SHORT_NAME: str` (optional) – short display name for sensor state
- `SUPPORTS_INCIDENT_BODY: ClassVar[bool]` (default `True`)
- `async def detect(session, url, timeout) -> bool` – return `True` if the URL belongs to this provider
- `async def fetch(session, url, timeout) -> StatusPageData`

### Provider volgorde
De volgorde in `PROVIDERS` in `providers/__init__.py` is belangrijk:
- **Atlassian vóór Instatus** — beide gebruiken `/summary.json`; Atlassian moet eerst worden geprobeerd
- **Cachet als laatste** — vereist een self-hosted ping endpoint

### Nieuwe provider toevoegen
1. Maak `providers/<naam>.py` met `detect()` en `fetch()`
2. Voeg `PROVIDER_<NAAM>` toe aan `const.py`
3. Importeer de klasse in `providers/__init__.py` en voeg hem toe aan `PROVIDERS`
4. Voeg een MDI-fallbackpictogram toe aan `_PROVIDER_ICONS` in `sensor.py`
5. Voeg een SVG-logo toe aan `providers/logos/<naam>.svg`

### Data model
Dataclasses gedefinieerd in `providers/base.py` — providers moeten deze retourneren:

```
StatusPageData
├── page: PageInfo          name, url, updated_at
├── status: OverallStatus   indicator (none/minor/major/critical), description
├── incidents: list[Incident]
│     id, name, status, impact, shortlink, started_at, updated_at, body
├── scheduled_maintenances: list[Maintenance]
│     id, name, status, impact, shortlink, scheduled_for, scheduled_until
└── components: list[Component]
      id, name, status, description, group, group_id, updated_at, showcase
```

Alle tijdstempels als ISO-8601 string (JSON-serializable).

## Known pitfalls
- `suggested_object_id` is a **read-only property** on HA's `Entity` — always set `_attr_suggested_object_id`.
- Entity IDs are migrated in `_async_migrate_entity_ids()` in `__init__.py` for backwards compat with older installs. The migration runs both before and after `async_forward_entry_setups` to handle first-time setup correctly.
- Static sensors are only added after `coordinator.data` is available (first successful fetch).
- Component sensors are added dynamically on coordinator updates; `known_component_ids` prevents duplicates.

## Versioning
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

## Toekomstige providers (onderzocht, nog niet geïmplementeerd)

### Better Stack
- **Website:** https://betterstack.com
- **API:** Voeg `/index.json` toe aan elke status page URL. Geen auth nodig.
- **Formaat:** JSON:API. `data.attributes.aggregate_state`: `operational`, `degraded`, `downtime`, `maintenance`. `included[]` bevat secties, resources (monitors) en status reports (incidents + updates).
- **Detectie:** response bevat `data.type == "status-page"` of `data.attributes.aggregate_state`.
- **Voorbeelden:** Geen bekende publieke URLs gevonden (custom domains, geen vast patroon).

### Hyperping
- **Website:** https://hyperping.com
- **API:** Voeg `/status.json` toe aan elke status page URL. Geen auth nodig.
- **Formaat:** Plat JSON. Top-level `indicator`: `up`, `down`, `outage`, `maintenance`. `services[]` met `name`, `indicator`, `status`.
- **Detectie:** response bevat root-level `indicator` en `services` array.
- **Voorbeelden:** Geen bekende publieke URLs gevonden.

### StatusPal
- **Website:** https://statuspal.io (US) / https://statuspal.eu (EU)
- **API:** Centraal eindpunt (niet op de status page URL zelf):
  - `https://statuspal.io/api/v2/status_pages/{subdomain}/summary`
  - `https://statuspal.eu/api/v2/status_pages/{subdomain}/summary`
- **Formaat:** REST JSON. Bevat status page info, volledige service-hiërarchie, actieve incidenten met timeline-updates, actieve en geplande onderhoudvensters.
- **Detectie:** lastig vanuit de URL — vereist extractie van de subdomain uit de status page HTML of een vaste `*.statuspal.io` / `*.statuspal.eu` URL.
- **Voorbeelden:**
  - https://exoscalestatus.statuspal.eu (Exoscale)

### Niet geschikt / afgevallen
- **Uptime Kuma** — al een uitgebreide bestaande HA-integratie voor.
- **Freshstatus** — stopgezet per 31-03-2026.
- **Cronitor** — alleen RSS, geen JSON API.
- **Upptime** — GitHub-repo per instantie, geen consistent eindpunt.
- **StatusHub** — vereist API-sleutel.
- **Hund** — alleen SSE stream, geen gewone REST polling.
- **OneUptime** — gebruikt POST + statusPageId (niet zichtbaar in URL).

## Git workflow
- Main branch: `statuspage-monitor-main`

## Bekende kleine tekortkomingen (codebase review 2026-03-14)

- **`nl.json` mist `"name"` voor `overall_status`** — valt terug op Engelse naam "Overall Status". Fix: voeg `"name": "Algehele status"` toe onder `entity.sensor.overall_status` in `nl.json`.
- **Dubbele HTTP-fetch per poll-cyclus** bij Cachet, Status.io en UptimeRobot: `fetch()` roept opnieuw `_get_api_prefix` / `_fetch_page_html` / `_fetch_page_info` aan (idem als tijdens `detect()`). Architectureel onvermijdelijk met huidig design; bewust geaccepteerd.
- **`asyncio.sleep(0)` als gather-placeholder** in `cachet.py` (regels ~250, ~257). Werkt prima maar is onconventioneel.
- **`instatus.py` gebruikt `datetime.fromisoformat()` direct** voor het berekenen van `scheduled_until`. Valt buiten de spirit van de dt_util-regel (die geldt voor `datetime.now()`); geen functioneel probleem.
- **`sorry.py` mapt `"maintenance"` → `"minor"` indicator** voor de overall status. Bewuste keuze; alternatief is `"none"` (onderhoud = geen storing).

## HA Iron Law
- ALTIJD async/await gebruiken
- Timestamps via dt_util, nooit datetime.now()
- Entiteit-attributen altijd JSON-serializable
- DataUpdateCoordinator pattern voor polling
