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
  • Atlassian Statuspage (statuspage.io) – full support
  • Status.io – planned
  • UptimeRobot Status Pages – planned

The provider for each configured URL is auto-detected during setup.
"""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import CONF_PROVIDER, DOMAIN
from .coordinator import StatusPageMonitorCoordinator
from .providers import get_provider

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up StatusPage Monitor from a config entry."""
    provider_class = get_provider(entry.data.get(CONF_PROVIDER))
    coordinator = StatusPageMonitorCoordinator(hass, entry, provider_class)

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
