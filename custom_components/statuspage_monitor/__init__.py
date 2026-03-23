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
  • Statuspage.io (statuspage.io)
  • Status.io
  • UptimeRobot Status Pages
  • Instatus (instatus.com)
  • Sorry™ (sorryapp.com)
  • Cachet (self-hosted)

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
    """Rename legacy entity IDs to their current canonical form (single pass).

    Migrations applied per entity:

    1. Missing ``statuspage_`` prefix — older versions did not set
       ``suggested_object_id``, so HA generated IDs from the device + entity
       name (e.g. ``sensor.claude_overall_status``).

    2. Dutch ``actief_incident_tekst`` suffix — briefly shipped with a Dutch
       display name causing HA to derive a Dutch entity ID.

    3. Intermediate ``active_incident_body`` suffix — short-lived English name
       before the sensor was renamed to ``active_incident_description``.
    """
    ent_reg = er.async_get(hass)

    _SUFFIX_RENAMES = {
        "_actief_incident_tekst": "_active_incident_description",
        "_active_incident_body": "_active_incident_description",
    }

    for entity_entry in er.async_entries_for_config_entry(ent_reg, entry.entry_id):
        entity_id = entity_entry.entity_id
        domain, object_id = entity_id.split(".", 1)

        # Migration 1: add missing statuspage_ prefix.
        if not object_id.startswith("statuspage_"):
            entity_id = f"{domain}.statuspage_{object_id}"

        # Migrations 2 & 3: rename legacy suffixes.
        for old_suffix, new_suffix in _SUFFIX_RENAMES.items():
            if entity_id.endswith(old_suffix):
                entity_id = entity_id[: -len(old_suffix)] + new_suffix
                break

        if entity_id != entity_entry.entity_id and ent_reg.async_get(entity_id) is None:
            ent_reg.async_update_entity(entity_entry.entity_id, new_entity_id=entity_id)
            _LOGGER.info("Migrated entity ID %s → %s", entity_entry.entity_id, entity_id)


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

    # Run migration again after platform setup so that entity IDs created during
    # a first-time setup (when no entities existed yet for the pre-setup pass)
    # are immediately corrected to the canonical statuspage_ prefix.
    await _async_migrate_entity_ids(hass, entry)

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
