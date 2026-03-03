"""Data update coordinator for Atlassian Statuspage."""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from urllib.parse import urlparse

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    API_SUMMARY_PATH,
    API_TIMEOUT,
    CONF_SCAN_INTERVAL,
    CONF_URL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class StatuspageCoordinator(DataUpdateCoordinator):
    """Coordinator to fetch data from an Atlassian Statuspage JSON API.

    Uses /api/v2/summary.json which returns page metadata, all component
    statuses, active incidents and upcoming scheduled maintenances in a
    single HTTP request – minimising the number of calls to the remote API.

    Atlassian Statuspage does not publish hard rate-limits for the public
    JSON API, but polling faster than 30 seconds is considered impolite and
    may cause temporary IP-level throttling.  The default poll interval is
    60 seconds; the minimum is enforced at 30 seconds via the config flow.
    """

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialise the coordinator."""
        self._url = entry.data[CONF_URL].rstrip("/")
        scan_interval = entry.options.get(
            CONF_SCAN_INTERVAL,
            entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
        )
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{entry.entry_id}",
            update_interval=timedelta(seconds=scan_interval),
        )

    @property
    def status_page_url(self) -> str:
        """Return the base URL of the status page."""
        return self._url

    async def _async_update_data(self) -> dict:
        """Fetch data from the Statuspage summary endpoint."""
        api_url = f"{self._url}{API_SUMMARY_PATH}"
        session = async_get_clientsession(self.hass)

        try:
            async with asyncio.timeout(API_TIMEOUT):
                async with session.get(
                    api_url,
                    headers={"Accept": "application/json"},
                ) as response:
                    if response.status == 401:
                        raise ConfigEntryAuthFailed(
                            f"Authentication failed for {api_url}"
                        )
                    if response.status == 404:
                        raise UpdateFailed(
                            f"Statuspage API not found at {api_url}. "
                            "Check that the URL points to an Atlassian Statuspage."
                        )
                    response.raise_for_status()
                    data = await response.json(content_type=None)

        except asyncio.TimeoutError as err:
            raise UpdateFailed(
                f"Timeout fetching Statuspage data from {api_url}"
            ) from err
        except aiohttp.ClientResponseError as err:
            raise UpdateFailed(
                f"HTTP error {err.status} fetching Statuspage data from {api_url}"
            ) from err
        except aiohttp.ClientError as err:
            raise UpdateFailed(
                f"Error communicating with Statuspage at {api_url}: {err}"
            ) from err

        _LOGGER.debug(
            "Fetched Statuspage data from %s: status=%s, components=%d, "
            "incidents=%d, maintenances=%d",
            api_url,
            data.get("status", {}).get("indicator", "unknown"),
            len(data.get("components", [])),
            len(data.get("incidents", [])),
            len(data.get("scheduled_maintenances", [])),
        )
        return data


def validate_statuspage_url(url: str) -> str:
    """Validate and normalise a Statuspage base URL.

    Returns the normalised URL string or raises ValueError.
    """
    url = url.strip().rstrip("/")
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("URL must start with http:// or https://")
    if not parsed.netloc:
        raise ValueError("URL must include a hostname")
    return url
