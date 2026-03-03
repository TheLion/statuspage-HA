"""Data update coordinator for StatusPage Monitor."""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from urllib.parse import urlparse

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    API_TIMEOUT,
    CONF_SCAN_INTERVAL,
    CONF_URL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)
from .providers.base import StatusPageData

_LOGGER = logging.getLogger(__name__)


class StatusPageMonitorCoordinator(DataUpdateCoordinator[StatusPageData]):
    """Coordinator that fetches status data via a pluggable provider.

    The *provider_class* argument must satisfy the StatusPageProvider Protocol
    defined in ``providers/base.py``.  Each provider is responsible for
    fetching data from its platform and returning a normalised StatusPageData.
    """

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        provider_class: type,
    ) -> None:
        """Initialise the coordinator with a specific provider."""
        self._url = entry.data[CONF_URL].rstrip("/")
        self._provider = provider_class
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

    async def _async_update_data(self) -> StatusPageData:
        """Fetch data from the status page via the configured provider."""
        session = async_get_clientsession(self.hass)
        try:
            return await self._provider.fetch(session, self._url, API_TIMEOUT)
        except asyncio.TimeoutError as err:
            raise UpdateFailed(
                f"Timeout fetching status data from {self._url}"
            ) from err
        except aiohttp.ClientResponseError as err:
            raise UpdateFailed(
                f"HTTP error {err.status} fetching status data from {self._url}"
            ) from err
        except aiohttp.ClientError as err:
            raise UpdateFailed(
                f"Error communicating with status page at {self._url}: {err}"
            ) from err


def validate_url(url: str) -> str:
    """Validate and normalise a status page base URL.

    Returns the normalised URL string or raises ValueError.
    """
    url = url.strip().rstrip("/")
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("URL must start with http:// or https://")
    if not parsed.netloc:
        raise ValueError("URL must include a hostname")
    return url
