"""Provider stub for UptimeRobot Status Pages (https://uptimerobot.com/status-pages/).

UptimeRobot status pages are hosted at custom domains or at
``https://stats.uptimerobot.com/{token}``.  Unlike Atlassian Statuspage,
they do not expose a simple public JSON API; the page content is rendered
client-side via JavaScript.

Two approaches to consider for implementation:
  A. Screen-scraping / HTML parsing
     - Fetch the page HTML
     - Parse the embedded JSON payload (often in a ``<script>`` tag as
       ``window.__NUXT__`` or similar)
     - Map monitor statuses to canonical Component.status values

  B. UptimeRobot API (requires API key)
     - ``GET https://api.uptimerobot.com/v2/getMonitors`` with an API key
     - This requires adding a ``CONF_API_KEY`` field to the config flow
       which changes the UX significantly

TODO: implement this provider
------------------------------
1. Decide on approach A or B above
2. Implement ``detect``:
   - Approach A: fetch HTML and look for UptimeRobot-specific markers
   - Approach B: validate that an API key + URL combination works
3. Implement ``fetch``:
   - Parse monitor states and map to ``StatusPageData``
   - Map UptimeRobot monitor statuses:
       2 (up)          → "operational"
       8 (seems down)  → "degraded_performance"
       9 (down)        → "major_outage"
       0 (paused)      → "under_maintenance"
4. Add ``UptimeRobotProvider`` to ``PROVIDERS`` in ``providers/__init__.py``
"""
from __future__ import annotations

from typing import ClassVar

import aiohttp

from .base import StatusPageData


class UptimeRobotProvider:
    """Provider for UptimeRobot Status Pages (not yet implemented)."""

    ID: ClassVar[str] = "uptimerobot"
    NAME: ClassVar[str] = "UptimeRobot"
    SHORT_NAME: ClassVar[str] = "UptimeRobot"
    LOGO_PATH: ClassVar[str] = "/statuspage_monitor/logos/uptimerobot.svg"

    @classmethod
    async def detect(
        cls,
        session: aiohttp.ClientSession,
        url: str,
        timeout: int,
    ) -> bool:
        raise NotImplementedError("UptimeRobot provider is not yet implemented")

    @classmethod
    async def fetch(
        cls,
        session: aiohttp.ClientSession,
        url: str,
        timeout: int,
    ) -> StatusPageData:
        raise NotImplementedError("UptimeRobot provider is not yet implemented")
