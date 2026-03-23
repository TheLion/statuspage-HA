"""Provider implementation for UptimeRobot Status Pages.

UptimeRobot status pages are hosted on custom domains or at
``https://stats.uptimerobot.com/{token}``.

Detection strategy
------------------
1. Fetch the page HTML at *url*.
2. Search for ``window.pspApiPath`` — present on every UptimeRobot status
   page and contains the full public API URL including the page token.

Public API (no authentication required)
----------------------------------------
The page HTML exposes two global JavaScript variables::

    window.pspApiPath    = 'https://status.uptimerobot.com/api/getMonitorList/{token}'
    window.eventsApiPath = 'https://status.uptimerobot.com/api/getEventFeed/{token}'

getMonitorList response structure (verified against status.uptimerobot.com)::

    {
      "status": "ok",
      "data": [
        {
          "monitorId":   778224452,
          "name":        "API v2",
          "statusClass": "success",   # see mapping below
          "groupId":     0,
          "groupName":   "Monitors (default)",
          "dailyRatios": [...],
          "30dRatio":    { "ratio": "99.974", "label": "excellent" },
          "lastDowntime": {
            "date":     "2026-02-25 21:03:53",
            "duration": 664,
            "reason":   "Incident detected"
          }
        }
      ]
    }

getEventFeed response structure::

    {
      "status": true,
      "results": [
        {
          "type":      "maintenance",    # "maintenance" | "incident" | "announcement"
          "id":        37371,
          "title":     "Planned maintenance window on February 9th",
          "content":   "...",
          "date":      "Feb 5, 2026",
          "time":      "16:30",
          "timestamp": 1770309000,
          "status":    2,               # 0=ongoing/upcoming, 2=completed
          "endDate":   null
        }
      ]
    }

statusClass mapping
-------------------
    =========== ======================= ========== =================
    statusClass UptimeRobot meaning     indicator  component_status
    =========== ======================= ========== =================
    success     Up                      none       operational
    warning     Seems down / degraded   minor      degraded_performance
    danger      Down                    major      major_outage
    paused      Paused / maintenance    none       under_maintenance
    =========== ======================= ========== =================

Overall indicator is derived from the worst monitor statusClass.
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

_PSP_API_PATH_RE = re.compile(r"window\.pspApiPath\s*=\s*['\"]([^'\"]+)['\"]")
_PSP_EVENTS_PATH_RE = re.compile(r"window\.eventsApiPath\s*=\s*['\"]([^'\"]+)['\"]")
_TITLE_RE = re.compile(r"<title[^>]*>([^<]+)</title>", re.IGNORECASE)

# Component status mapping
_STATUS_CLASS_TO_COMPONENT: dict[str, str] = {
    "success": "operational",
    "warning": "degraded_performance",
    "danger":  "major_outage",
    "paused":  "under_maintenance",
}

# Severity for deriving the overall indicator
_STATUS_CLASS_SEVERITY: dict[str, int] = {
    "success": 0,
    "paused":  0,
    "warning": 1,
    "danger":  2,
}
_SEVERITY_TO_INDICATOR = {0: "none", 1: "minor", 2: "major"}


def _hostname_name(url: str) -> str:
    host = urlparse(url).netloc
    for prefix in ("status.", "statuspage.", "stats.", "www."):
        if host.startswith(prefix):
            host = host[len(prefix):]
    return host


async def _fetch_page_info(
    session: aiohttp.ClientSession,
    url: str,
    timeout: int,
) -> tuple[str | None, str | None, str | None]:
    """Return (api_path, events_path, page_name) from the page HTML."""
    try:
        async with asyncio.timeout(timeout):
            async with session.get(url) as resp:
                if resp.status != 200:
                    return None, None, None
                html = await resp.text()
        api_m = _PSP_API_PATH_RE.search(html)
        events_m = _PSP_EVENTS_PATH_RE.search(html)
        api_path = api_m.group(1) if api_m else None
        events_path = events_m.group(1) if events_m else None
        title_m = _TITLE_RE.search(html)
        title = title_m.group(1).strip() if title_m else None
        if title:
            for suffix in (" | Status", " Status Page", " - Status", " \u2013 Status"):
                if title.endswith(suffix):
                    title = title[: -len(suffix)].strip()
        page_name = title or _hostname_name(url)
        return api_path, events_path, page_name
    except Exception as err:  # noqa: BLE001
        _LOGGER.debug("UptimeRobot: HTML fetch failed for %s: %s", url, err)
        return None, None, None


class UptimeRobotProvider:
    """Provider for UptimeRobot Status Pages."""

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
        """Return True if *url* is an UptimeRobot status page."""
        api_path, _, _ = await _fetch_page_info(session, url, timeout)
        if not api_path:
            _LOGGER.debug("UptimeRobot detect: no pspApiPath in HTML at %s", url)
            return False
        return True

    @classmethod
    async def fetch(
        cls,
        session: aiohttp.ClientSession,
        url: str,
        timeout: int,
        *,
        meta: dict[str, str] | None = None,
    ) -> StatusPageData:
        """Fetch current status and return normalised StatusPageData."""
        # Use cached metadata when available to skip the HTML fetch.
        if meta and meta.get("api_path"):
            api_path = meta["api_path"]
            events_path = meta.get("events_path")
            page_name = meta.get("page_name") or _hostname_name(url)
        else:
            api_path, events_path, page_name = await _fetch_page_info(session, url, timeout)
            if not api_path:
                raise ValueError(f"Could not extract UptimeRobot API path from {url}")

        # Fetch monitors and events in parallel.
        async with asyncio.timeout(timeout):
            monitors_resp, events_resp = await asyncio.gather(
                session.get(api_path, headers=_HEADERS),
                session.get(events_path, headers=_HEADERS) if events_path else asyncio.sleep(0),
                return_exceptions=True,
            )

        monitors_raw: list[dict] = []
        if not isinstance(monitors_resp, Exception):
            async with monitors_resp as resp:
                if resp.status == 200:
                    data = await resp.json(content_type=None)
                    monitors_raw = data.get("data", [])

        events_raw: list[dict] = []
        if events_path and not isinstance(events_resp, Exception):
            async with events_resp as resp:
                if resp.status == 200:
                    data = await resp.json(content_type=None)
                    events_raw = data.get("results", [])

        # Derive overall status from worst monitor.
        worst_severity = max(
            (_STATUS_CLASS_SEVERITY.get(m.get("statusClass", "success"), 0) for m in monitors_raw),
            default=0,
        )
        indicator = _SEVERITY_TO_INDICATOR.get(worst_severity, "none")

        page = PageInfo(name=page_name or _hostname_name(url), url=url)
        status = OverallStatus(indicator=indicator)

        # Components — one per monitor.
        components: list[Component] = [
            Component(
                id=str(m.get("monitorId", idx)),
                name=m.get("name", ""),
                status=_STATUS_CLASS_TO_COMPONENT.get(
                    m.get("statusClass", "success"), "operational"
                ),
                group_id=str(m["groupId"]) if m.get("groupId") else None,
                group=False,
            )
            for idx, m in enumerate(monitors_raw)
        ]

        # Events — map to Incident or Maintenance based on type.
        # Events with status 2 are completed/resolved and are skipped.
        incidents: list[Incident] = []
        maintenances: list[Maintenance] = []
        for ev in events_raw:
            ev_type = ev.get("type", "")
            ev_status = ev.get("status", 0)
            ev_id = str(ev.get("id", ""))
            ev_title = ev.get("title", "")
            ev_body = ev.get("content") or ev.get("description")
            dt_str = f"{ev.get('date', '')} {ev.get('time', '')}".strip() or None

            if ev_type == "maintenance":
                if ev_status == 2:   # completed
                    continue
                maintenances.append(Maintenance(
                    id=ev_id,
                    name=ev_title,
                    status="in_progress" if ev_status == 1 else "scheduled",
                    impact="none",
                    scheduled_for=dt_str,
                    scheduled_until=None,
                ))
            elif ev_type == "incident":
                if ev_status == 2:   # resolved
                    continue
                incidents.append(Incident(
                    id=ev_id,
                    name=ev_title,
                    status="investigating",
                    impact="minor" if worst_severity <= 1 else "major",
                    shortlink=url,
                    started_at=dt_str,
                    body=ev_body,
                ))

        provider_meta = {"api_path": api_path, "page_name": page_name or ""}
        if events_path:
            provider_meta["events_path"] = events_path

        return StatusPageData(
            page=page,
            status=status,
            incidents=incidents,
            scheduled_maintenances=maintenances,
            components=components,
            provider_meta=provider_meta,
        )
