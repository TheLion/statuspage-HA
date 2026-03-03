"""Provider registry for Status Page Monitor.

Only *fully implemented* providers are listed in PROVIDERS.  Stub providers
(status_io, uptimerobot) are importable but not registered here – add them
once their detect() and fetch() methods are implemented.

Adding a new provider
---------------------
1. Create ``providers/<name>.py`` implementing the StatusPageProvider Protocol.
2. Import the class below and add it to PROVIDERS.
3. That's it – auto-detection and the config flow pick it up automatically.
"""
from __future__ import annotations

import logging

import aiohttp

from .base import StatusPageData, StatusPageProvider  # noqa: F401 – re-exported
from .statuspage_io import StatuspageIoProvider

_LOGGER = logging.getLogger(__name__)

# Ordered list of active providers.  Detection is tried in this order.
PROVIDERS: list[type[StatuspageIoProvider]] = [
    StatuspageIoProvider,
    # Add new providers here, e.g.:
    # StatusIoProvider,
    # UptimeRobotProvider,
]

PROVIDERS_BY_ID: dict[str, type] = {p.ID: p for p in PROVIDERS}


async def detect_provider(
    session: aiohttp.ClientSession,
    url: str,
    timeout: int,
) -> type | None:
    """Try each registered provider and return the first one that matches *url*.

    Returns None if no provider recognises the URL.
    """
    for provider in PROVIDERS:
        _LOGGER.debug("Trying provider %s for %s", provider.NAME, url)
        if await provider.detect(session, url, timeout):
            _LOGGER.debug("Detected provider %s for %s", provider.NAME, url)
            return provider
    return None


def get_provider(provider_id: str | None) -> type:
    """Return the provider class for *provider_id*, defaulting to Statuspage.io."""
    if provider_id and provider_id in PROVIDERS_BY_ID:
        return PROVIDERS_BY_ID[provider_id]
    return StatuspageIoProvider
