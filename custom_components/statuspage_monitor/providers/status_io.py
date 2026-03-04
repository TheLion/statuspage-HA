"""Provider implementation for Status.io (https://status.io).

Detection strategy
------------------
1. Fetch the page HTML at *url*.
2. Search for ``var statuspageId = '([a-f0-9]{24})'`` — embedded in every
   Status.io ``<script>`` block.
3. Call ``https://api.status.io/1.0/status/{page_id}`` — verify HTTP 200
   with a ``"result"`` key in the body.

API reference
-------------
GET https://api.status.io/1.0/status/{page_id}  — no authentication required.

Response structure (verified against status.status.io)::

    {
      "result": {
        "status_overall": {
          "updated":     "2026-03-04T15:00:04.907Z",
          "status":      "Operational",
          "status_code": 100
        },
        "status": [
          {
            "id":          "52cbb6a6e746d36b13000116",
            "name":        "Public Status Pages",
            "status_code": 100,
            "updated":     "2026-02-18T20:43:20.268Z",
            "containers":  [...]
          }
        ],
        "incidents": [
          {
            "_id":           "...",
            "name":          "Incident title",
            "status_code":   100,
            "datetime_open": "...",
            "messages": [
              { "details": "Update text", "state": 100, "status": 300, "datetime": "..." }
            ],
            "components_affected": [...],
            "containers_affected": [...]
          }
        ],
        "maintenance": {
          "active": [...],
          "upcoming": [
            {
              "_id":                    "...",
              "name":                   "Deploy Version X",
              "datetime_planned_start": "2026-03-04T23:30:00.000Z",
              "datetime_planned_end":   "2026-03-04T23:45:00.000Z"
            }
          ]
        }
      }
    }

Status code mapping
-------------------
    ===== ===================== ========== =======================
    Code  Status.io name        indicator  component_status
    ===== ===================== ========== =======================
    100   Operational           none       operational
    200   Maintenance           none       under_maintenance
    300   Degraded              minor      degraded_performance
    400   Partial Outage        major      partial_outage
    500   Service Disruption    critical   major_outage
    600   Security Event        critical   major_outage
    ===== ===================== ========== =======================

Incident status_code values: 100=Investigating, 200=Identified,
300=Monitoring, 400=Resolved (skip resolved).
"""
from __future__ import annotations

import asyncio
import logging
import re
from typing import ClassVar
from urllib.parse import urlparse

import aiohttp

from .base import (
    Component,
    Incident,
    Maintenance,
    OverallStatus,
    PageInfo,
    StatusPageData,
)

_LOGGER = logging.getLogger(__name__)

_HEADERS = {"Accept": "application/json"}
_API_BASE = "https://api.status.io/1.0"

_PAGE_ID_RE = re.compile(r"var\s+statuspageId\s*=\s*['\"]([a-f0-9]{24})['\"]")
_TITLE_RE = re.compile(r"<title[^>]*>([^<]+)</title>", re.IGNORECASE)

_CODE_TO_INDICATOR: dict[int, str] = {
    100: "none",
    200: "none",
    300: "minor",
    400: "major",
    500: "critical",
    600: "critical",
}

_CODE_TO_COMPONENT_STATUS: dict[int, str] = {
    100: "operational",
    200: "under_maintenance",
    300: "degraded_performance",
    400: "partial_outage",
    500: "major_outage",
    600: "major_outage",
}

_INCIDENT_CODE_TO_STATUS: dict[int, str] = {
    100: "investigating",
    200: "identified",
    300: "monitoring",
    400: "resolved",
}


def _hostname_name(url: str) -> str:
    host = urlparse(url).netloc
    for prefix in ("status.", "statuspage.", "www."):
        if host.startswith(prefix):
            host = host[len(prefix):]
    return host


async def _fetch_page_html(
    session: aiohttp.ClientSession,
    url: str,
    timeout: int,
) -> tuple[str | None, str | None]:
    """Return (page_id, page_name) extracted from the page HTML."""
    try:
        async with asyncio.timeout(timeout):
            async with session.get(url) as resp:
                if resp.status != 200:
                    return None, None
                html = await resp.text()
        id_match = _PAGE_ID_RE.search(html)
        page_id = id_match.group(1) if id_match else None
        title_m = _TITLE_RE.search(html)
        title = title_m.group(1).strip() if title_m else None
        if title:
            for suffix in (" | Status", " Status Page", " - Status", " \u2013 Status"):
                if title.endswith(suffix):
                    title = title[: -len(suffix)].strip()
        return page_id, title or _hostname_name(url)
    except Exception as err:  # noqa: BLE001
        _LOGGER.debug("Status.io: HTML fetch failed for %s: %s", url, err)
        return None, None


class StatusIoProvider:
    """Provider for the Status.io platform."""

    ID: ClassVar[str] = "status_io"
    NAME: ClassVar[str] = "Status.io"
    SHORT_NAME: ClassVar[str] = "Status.io"
    LOGO_PATH: ClassVar[str] = "/statuspage_monitor/logos/status_io.svg"

    @classmethod
    async def detect(
        cls,
        session: aiohttp.ClientSession,
        url: str,
        timeout: int,
    ) -> bool:
        """Return True if *url* is a Status.io hosted status page."""
        page_id, _ = await _fetch_page_html(session, url, timeout)
        if not page_id:
            _LOGGER.debug("Status.io detect: no statuspageId in HTML at %s", url)
            return False
        api_url = f"{_API_BASE}/status/{page_id}"
        try:
            async with asyncio.timeout(timeout):
                async with session.get(api_url, headers=_HEADERS) as resp:
                    if resp.status != 200:
                        _LOGGER.debug(
                            "Status.io detect: API %s -> HTTP %s", api_url, resp.status
                        )
                        return False
                    data = await resp.json(content_type=None)
                    return "result" in data
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug(
                "Status.io detect: API call failed %s: %s: %s",
                api_url, type(err).__name__, err,
            )
            return False

    @classmethod
    async def fetch(
        cls,
        session: aiohttp.ClientSession,
        url: str,
        timeout: int,
    ) -> StatusPageData:
        """Fetch current status and return normalised StatusPageData."""
        page_id, page_name = await _fetch_page_html(session, url, timeout)
        if not page_id:
            raise ValueError(f"Could not extract Status.io page_id from {url}")

        async with asyncio.timeout(timeout):
            async with session.get(
                f"{_API_BASE}/status/{page_id}", headers=_HEADERS
            ) as resp:
                resp.raise_for_status()
                raw = await resp.json(content_type=None)

        result = raw.get("result", {})
        overall_raw = result.get("status_overall", {})
        status_code = int(overall_raw.get("status_code", 100))

        page = PageInfo(
            name=page_name or _hostname_name(url),
            url=url,
            updated_at=overall_raw.get("updated"),
        )
        status = OverallStatus(
            indicator=_CODE_TO_INDICATOR.get(status_code, "none"),
            description=overall_raw.get("status"),
        )

        components: list[Component] = []
        for item in result.get("status", []):
            comp_code = int(item.get("status_code", 100))
            components.append(Component(
                id=item.get("id", ""),
                name=item.get("name", ""),
                status=_CODE_TO_COMPONENT_STATUS.get(comp_code, "operational"),
                updated_at=item.get("updated"),
            ))

        incidents: list[Incident] = []
        for inc in result.get("incidents", []):
            inc_code = int(inc.get("status_code", 400))
            if inc_code >= 400:
                continue
            messages = inc.get("messages") or []
            latest = messages[0] if messages else {}
            impact = _CODE_TO_INDICATOR.get(status_code, "minor") or "minor"
            incidents.append(Incident(
                id=inc.get("_id", ""),
                name=inc.get("name", ""),
                status=_INCIDENT_CODE_TO_STATUS.get(inc_code, "investigating"),
                impact=impact,
                shortlink=url,
                started_at=inc.get("datetime_open"),
                updated_at=latest.get("datetime"),
                body=latest.get("details"),
            ))

        maintenances: list[Maintenance] = []
        maint_raw = result.get("maintenance", {})
        for m in maint_raw.get("active", []):
            maintenances.append(Maintenance(
                id=m.get("_id", ""),
                name=m.get("name", ""),
                status="in_progress",
                impact="none",
                scheduled_for=m.get("datetime_planned_start"),
                scheduled_until=m.get("datetime_planned_end"),
            ))
        for m in maint_raw.get("upcoming", []):
            maintenances.append(Maintenance(
                id=m.get("_id", ""),
                name=m.get("name", ""),
                status="scheduled",
                impact="none",
                scheduled_for=m.get("datetime_planned_start"),
                scheduled_until=m.get("datetime_planned_end"),
            ))

        return StatusPageData(
            page=page,
            status=status,
            incidents=incidents,
            scheduled_maintenances=maintenances,
            components=components,
        )
