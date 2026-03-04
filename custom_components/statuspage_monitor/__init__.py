"""StatusPage Monitor integration for Home Assistant.

Monitors any compatible status page and exposes its health data as HA sensors:
  • Overall status indicator (none / minor / major / critical)
  • Active incidents count with details
  • Scheduled maintenances count with details
  • Per-component status

Multiple status pages can be monitored by adding separate integration entries
through the UI (Settings → Devices & Services → Add Integration).

Supported platforms
-------------------
  • Statuspage.io (statuspage.io) – full support
  • Status.io – planned
  • UptimeRobot Status Pages – planned

The provider for each configured URL is auto-detected during setup.
"""
from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import CONF_PROVIDER, DOMAIN
from .coordinator import StatusPageMonitorCoordinator
from .providers import get_provider

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]

_LOGOS_URL_PATH = "/statuspage_monitor/logos"
_LOGOS_DIR = Path(__file__).parent / "providers" / "logos"


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Register static logo assets so entity_picture URLs resolve inside HA."""
    await hass.http.async_register_static_paths(
        [StaticPathConfig(_LOGOS_URL_PATH, str(_LOGOS_DIR), cache_headers=True)]
    )
    return True


async def _async_migrate_entity_ids(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Rename legacy entity IDs to their current canonical form.

    Three migrations are applied in order:

    1. Missing ``statuspage_`` prefix — older versions did not set
       ``suggested_object_id``, so HA generated IDs from the device + entity
       name (e.g. ``sensor.claude_overall_status``).  These are renamed to
       include the prefix (``sensor.statuspage_claude_overall_status``).

    2. Dutch ``actief_incident_tekst`` suffix — the active-incident sensor was
       briefly shipped with a Dutch display name ("Actief incident – tekst")
       and no ``suggested_object_id``, causing HA to derive a Dutch entity ID.
       These are renamed directly to the canonical ``active_incident_description``
       suffix.

    3. Intermediate ``active_incident_body`` suffix — a short-lived English name
       before the sensor was renamed to ``active_incident_description``.
    """
    ent_reg = er.async_get(hass)

    # Pass 1: add missing statuspage_ prefix.
    for entity_entry in er.async_entries_for_config_entry(ent_reg, entry.entry_id):
        domain, object_id = entity_entry.entity_id.split(".", 1)
        if object_id.startswith("statuspage_"):
            continue
        new_entity_id = f"{domain}.statuspage_{object_id}"
        if ent_reg.async_get(new_entity_id) is None:
            ent_reg.async_update_entity(entity_entry.entity_id, new_entity_id=new_entity_id)
            _LOGGER.info("Migrated entity ID %s → %s", entity_entry.entity_id, new_entity_id)

    # Pass 2: rename Dutch suffix directly to current canonical English suffix.
    for entity_entry in er.async_entries_for_config_entry(ent_reg, entry.entry_id):
        if not entity_entry.entity_id.endswith("_actief_incident_tekst"):
            continue
        new_entity_id = entity_entry.entity_id.replace(
            "_actief_incident_tekst", "_active_incident_description"
        )
        if ent_reg.async_get(new_entity_id) is None:
            ent_reg.async_update_entity(entity_entry.entity_id, new_entity_id=new_entity_id)
            _LOGGER.info("Migrated entity ID %s → %s", entity_entry.entity_id, new_entity_id)

    # Pass 3: rename intermediate active_incident_body suffix to active_incident_description.
    for entity_entry in er.async_entries_for_config_entry(ent_reg, entry.entry_id):
        if not entity_entry.entity_id.endswith("_active_incident_body"):
            continue
        new_entity_id = entity_entry.entity_id.replace(
            "_active_incident_body", "_active_incident_description"
        )
        if ent_reg.async_get(new_entity_id) is None:
            ent_reg.async_update_entity(entity_entry.entity_id, new_entity_id=new_entity_id)
            _LOGGER.info("Migrated entity ID %s → %s", entity_entry.entity_id, new_entity_id)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up StatusPage Monitor from a config entry."""
    provider_class = get_provider(entry.data.get(CONF_PROVIDER))
    coordinator = StatusPageMonitorCoordinator(hass, entry, provider_class)

    # Perform the first refresh; raises ConfigEntryNotReady on failure which
    # causes HA to retry setup automatically.
    await coordinator.async_config_entry_first_refresh()

    # Rename legacy entity IDs (missing the statuspage_ prefix) before
    # the platform sets up its entities.
    await _async_migrate_entity_ids(hass, entry)

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Re-create the coordinator when the poll interval changes via options.
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the integration entry when options are changed."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
