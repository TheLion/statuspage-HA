"""Provider implementation for Instatus (https://instatus.com).

Instatus is a hosted status-page platform used by many SaaS services.
Pages are hosted on custom domains or on ``*.instatus.com`` subdomains.

Detection strategy
------------------
GET {url}/summary.json

- Returns HTTP 200 for valid Instatus pages.
- The JSON body contains a ``"page"`` object with a ``"status"`` field
  whose value is one of ``"UP"``, ``"HASISSUES"``, or ``"UNDERMAINTENANCE"``.
- Instatus pages do NOT have a root-level ``"components"`` key — this
  distinguishes them from Atlassian Statuspage (/api/v2/summary.json which
  DOES have ``"components"`` at root level).
- Try Atlassian Statuspage detection first; Instatus uses the same path
  ``/summary.json`` without the ``/api/v2`` prefix.

API endpoints (no authentication required)
-------------------------------------------
- Summary:    GET {url}/summary.json
- Components: GET {url}/v2/components.json
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import ClassVar

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

_SUMMARY_PATH = "/summary.json"
_COMPONENTS_PATH = "/v2/components.json"
_HEADERS = {"Accept": "application/json"}

# page.status → OverallStatus.indicator
_STATUS_MAP: dict[str, str] = {
    "UP": "none",
    "HASISSUES": "major",
    "UNDERMAINTENANCE": "none",  # maintenances tracked separately
}

# component.status → Component.status
_COMPONENT_STATUS_MAP: dict[str, str] = {
    "OPERATIONAL": "operational",
    "DEGRADEDPERFORMANCE": "degraded_performance",
    "PARTIALOUTAGE": "partial_outage",
    "MAJOROUTAGE": "major_outage",
    "UNDERMAINTENANCE": "under_maintenance",
}

# incident.impact → Incident.impact (our canonical values)
_INCIDENT_IMPACT_MAP: dict[str, str] = {
    "MINOROUTAGE": "minor",
    "PARTIALOUTAGE": "minor",
    "MAJOROUTAGE": "major",
    "UNDERMAINTENANCE": "none",
}

# activeIncidents already contains only active ones, but filter defensively
_RESOLVED_STATUSES = {"RESOLVED"}

# activeMaintenances already contains only active ones, but filter defensively
_COMPLETED_STATUSES = {"COMPLETED"}


class InstatusProvider:
    """Provider for the Instatus platform."""

    ID: ClassVar[str] = "instatus"
    NAME: ClassVar[str] = "Instatus"
    SHORT_NAME: ClassVar[str] = "Instatus"
    LOGO_PATH: ClassVar[str] = "/statuspage_monitor/logos/instatus.svg"
    SUPPORTS_INCIDENT_BODY: ClassVar[bool] = False

    @classmethod
    async def detect(
        cls,
        session: aiohttp.ClientSession,
        url: str,
        timeout: int,
    ) -> bool:
        """Return True if url is an Instatus status page.

        Atlassian Statuspage must be tried first — both use /summary.json.
        Instatus is distinguished by the absence of a root-level "components" key.
        """
        api_url = f"{url}{_SUMMARY_PATH}"
        try:
            async with asyncio.timeout(timeout):
                async with session.get(api_url, headers=_HEADERS) as resp:
                    if resp.status != 200:
                        _LOGGER.debug(
                            "Instatus detect: %s returned HTTP %s", api_url, resp.status
                        )
                        return False
                    data = await resp.json(content_type=None)
                    page_status = data.get("page", {}).get("status")
                    if page_status not in {"UP", "HASISSUES", "UNDERMAINTENANCE"}:
                        _LOGGER.debug(
                            "Instatus detect: unexpected page.status %r at %s",
                            page_status,
                            api_url,
                        )
                        return False
                    if "components" in data:
                        _LOGGER.debug(
                            "Instatus detect: root-level 'components' key found at %s"
                            " — likely Atlassian Statuspage",
                            api_url,
                        )
                        return False
                    return True
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug(
                "Instatus detect: exception fetching %s: %s: %s",
                api_url,
                type(err).__name__,
                err,
            )
            return False

    @classmethod
    async def fetch(
        cls,
        session: aiohttp.ClientSession,
        url: str,
        timeout: int,
    ) -> StatusPageData:
        """Fetch summary and components in parallel and return StatusPageData."""
        async with asyncio.timeout(timeout):
            summary, components_raw = await asyncio.gather(
                cls._get_json(session, f"{url}{_SUMMARY_PATH}"),
                cls._get_json(session, f"{url}{_COMPONENTS_PATH}"),
            )
        return cls._parse(summary, components_raw, url)

    @classmethod
    async def _get_json(cls, session: aiohttp.ClientSession, url: str) -> dict:
        async with session.get(url, headers=_HEADERS) as resp:
            resp.raise_for_status()
            return await resp.json(content_type=None)

    @classmethod
    def _parse(cls, summary: dict, components_raw: dict, url: str) -> StatusPageData:
        """Map raw Instatus JSON to the normalised StatusPageData model."""
        page_raw = summary.get("page", {})
        page_status = page_raw.get("status", "UP")

        components_list = components_raw.get("components", [])

        # Determine which component IDs are group headers:
        # a component is a group header if its ID is referenced as group.id by a child.
        group_ids: set[str] = {
            comp["group"]["id"]
            for comp in components_list
            if comp.get("group") and comp["group"].get("id")
        }

        return StatusPageData(
            page=PageInfo(
                name=page_raw.get("name") or url,
                url=url,
            ),
            status=OverallStatus(
                indicator=_STATUS_MAP.get(page_status, "none"),
            ),
            incidents=[
                Incident(
                    id=inc["id"],
                    name=inc.get("name", ""),
                    status=inc.get("status", ""),
                    impact=_INCIDENT_IMPACT_MAP.get(inc.get("impact", ""), "minor"),
                    shortlink=inc.get("url"),
                    started_at=inc.get("started"),
                    updated_at=inc.get("updatedAt"),
                )
                for inc in (summary.get("activeIncidents") or [])
                if inc.get("status") not in _RESOLVED_STATUSES
            ],
            scheduled_maintenances=[
                Maintenance(
                    id=mnt["id"],
                    name=mnt.get("name", ""),
                    status=mnt.get("status", ""),
                    impact="none",
                    shortlink=mnt.get("url"),
                    scheduled_for=mnt.get("start"),
                    scheduled_until=cls._maintenance_end(mnt),
                )
                for mnt in (summary.get("activeMaintenances") or [])
                if mnt.get("status") not in _COMPLETED_STATUSES
            ],
            components=[
                Component(
                    id=comp["id"],
                    name=comp.get("name", comp["id"]),
                    status=_COMPONENT_STATUS_MAP.get(
                        comp.get("status", ""), "operational"
                    ),
                    description=comp.get("description") or None,
                    group=comp["id"] in group_ids,
                    group_id=(
                        comp["group"]["id"] if comp.get("group") else None
                    ),
                )
                for comp in components_list
                if comp.get("id")
            ],
        )

    @staticmethod
    def _maintenance_end(mnt: dict) -> str | None:
        """Derive scheduled_until from start + duration (minutes, as string)."""
        start = mnt.get("start")
        if not start:
            return None
        try:
            duration_minutes = int(mnt.get("duration") or 0)
            if not duration_minutes:
                return None
            start_dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
            return (start_dt + timedelta(minutes=duration_minutes)).isoformat()
        except Exception:  # noqa: BLE001
            return None
