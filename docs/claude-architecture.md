# Architectuur — StatusPage Monitor

> Verplaatst vanuit `CLAUDE.md` op 2026-04-11. CLAUDE.md verwijst naar dit bestand.

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

## Data model

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
