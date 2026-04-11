# Known pitfalls & tekortkomingen — StatusPage Monitor

> Verplaatst vanuit `CLAUDE.md` op 2026-04-11. CLAUDE.md verwijst naar dit bestand.

## Algemene pitfalls

- `suggested_object_id` is a **read-only property** on HA's `Entity` — always set `_attr_suggested_object_id`.
- Entity IDs are migrated in `_async_migrate_entity_ids()` in `__init__.py` for backwards compat with older installs. The migration runs both before and after `async_forward_entry_setups` to handle first-time setup correctly.
- Static sensors are only added after `coordinator.data` is available (first successful fetch).
- Component sensors are added dynamically on coordinator updates; `known_component_ids` prevents duplicates.

## Bekende kleine tekortkomingen (codebase review 2026-03-14)

- **`nl.json` mist `"name"` voor `overall_status`** — valt terug op Engelse naam "Overall Status". Fix: voeg `"name": "Algehele status"` toe onder `entity.sensor.overall_status` in `nl.json`.
- **Dubbele HTTP-fetch per poll-cyclus** bij Cachet, Status.io en UptimeRobot: `fetch()` roept opnieuw `_get_api_prefix` / `_fetch_page_html` / `_fetch_page_info` aan (idem als tijdens `detect()`). Architectureel onvermijdelijk met huidig design; bewust geaccepteerd.
- **`asyncio.sleep(0)` als gather-placeholder** in `cachet.py` (regels ~250, ~257). Werkt prima maar is onconventioneel.
- **`instatus.py` gebruikt `datetime.fromisoformat()` direct** voor het berekenen van `scheduled_until`. Valt buiten de spirit van de dt_util-regel (die geldt voor `datetime.now()`); geen functioneel probleem.
- **`sorry.py` mapt `"maintenance"` → `"minor"` indicator** voor de overall status. Bewuste keuze; alternatief is `"none"` (onderhoud = geen storing).
