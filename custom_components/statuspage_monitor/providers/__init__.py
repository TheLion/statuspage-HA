"""Provider registry for StatusPage Monitor.

Adding a new provider
---------------------
1. Create ``providers/<name>.py`` implementing the StatusPageProvider Protocol.
2. Import the class below and add it to PROVIDERS.
3. That's it – auto-detection and the config flow pick it up automatically.
"""
from __future__ import annotations

import logging

import aiohttp

from .base import Component, StatusPageData, StatusPageProvider  # noqa: F401 – re-exported
from .cachet import CachetProvider
from .status_io import StatusIoProvider
from .statuspage_io import StatuspageIoProvider
from .uptimerobot import UptimeRobotProvider

_LOGGER = logging.getLogger(__name__)

# Ordered list of fully implemented providers.
# Atlassian is tried first (most common); Cachet last (requires self-hosted ping).
PROVIDERS: list[type] = [
    StatuspageIoProvider,
    StatusIoProvider,
    UptimeRobotProvider,
    CachetProvider,
]

PROVIDERS_BY_ID: dict[str, type] = {p.ID: p for p in PROVIDERS}


async def detect_provider(
    session: aiohttp.ClientSession,
    url: str,
    timeout: int,
) -> type | None:
    """Try each registered provider and return the first one that matches *url*.

    Returns None if no provider recognises the URL.  All detection attempts are
    logged at WARNING level so the Home Assistant logs give a clear diagnosis
    when a URL is rejected.
    """
    for provider in PROVIDERS:
        _LOGGER.debug("Trying provider %s for %s", provider.NAME, url)
        matched = await provider.detect(session, url, timeout)
        if matched:
            _LOGGER.info("Provider detected: %s → %s", url, provider.NAME)
            return provider
        _LOGGER.debug("Provider %s did not match %s", provider.NAME, url)

    _LOGGER.warning(
        "No supported status-page provider found for %s. "
        "Tried: %s. "
        "If this is a supported platform, check the URL and look for connection "
        "errors above this message.",
        url,
        ", ".join(p.NAME for p in PROVIDERS),
    )
    return None


def get_provider(provider_id: str | None) -> type:
    """Return the provider class for *provider_id*, defaulting to Statuspage.io."""
    if provider_id and provider_id in PROVIDERS_BY_ID:
        return PROVIDERS_BY_ID[provider_id]
    return StatuspageIoProvider
