"""Atlassian Statuspage integration for Home Assistant.

Fetches status, component health, active incidents and scheduled maintenances
from any Atlassian Statuspage instance (e.g. https://status.claude.com) via
the public JSON API (/api/v2/summary.json) and exposes them as HA sensors.

Multiple status pages can be monitored by adding separate integration entries
through the UI (Settings → Devices & Services → Add Integration).

Rate limiting
-------------
Atlassian Statuspage does not publish hard rate-limits for the public JSON
API, but their terms of service expect reasonable usage.  This integration
defaults to polling every 60 seconds (configurable, minimum 30 s).  All
data is retrieved in a single HTTP request per poll cycle.
"""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import CONF_SCAN_INTERVAL, CONF_URL, DOMAIN
from .coordinator import StatuspageCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Atlassian Statuspage from a config entry."""
    coordinator = StatuspageCoordinator(hass, entry)

    # Perform the first refresh; raises ConfigEntryNotReady on failure which
    # causes HA to retry setup automatically.
    await coordinator.async_config_entry_first_refresh()

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
