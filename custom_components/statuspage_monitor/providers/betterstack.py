"""Provider implementation for Better Stack (https://betterstack.com).

Better Stack hosts status pages on custom domains or ``*.betteruptime.com`` /
``*.betterstack.com`` subdomains.

Detection strategy
------------------
GET {url}/index.json

- Returns HTTP 200 with a JSON:API document for valid Better Stack pages.
- ``data.type == "status_page"`` confirms the platform.
- The endpoint differs from Atlassian (``/api/v2/summary.json``) and
  Instatus (``/summary.json``), so there is no detection conflict.

API endpoint (no authentication required)
-----------------------------------------
- Single document: ``GET {url}/index.json``
  Returns the page, sections, resources (components) and recent status_reports
  (incidents + maintenances) in one JSON:API response.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
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

_INDEX_PATH = "/index.json"
_HEADERS = {"Accept": "application/json"}

# data.attributes.aggregate_state → OverallStatus.indicator
# downtime → critical (Better Stack's worst state); maintenance is tracked
# separately via status_reports, so it maps to "none" at the indicator level
# (same convention as Atlassian/Instatus).
_STATUS_MAP: dict[str, str] = {
    "operational": "none",
    "degraded": "minor",
    "downtime": "critical",
    "maintenance": "none",
}

# resource.status → Component.status
_COMPONENT_STATUS_MAP: dict[str, str] = {
    "operational": "operational",
    "degraded": "degraded_performance",
    "downtime": "major_outage",
    "maintenance": "under_maintenance",
}

# Lifecycle states for status_reports with report_type == "manual" (incidents).
_RESOLVED_REPORT_STATES = {"resolved"}


class BetterStackProvider:
    """Provider for the Better Stack platform."""

    ID: ClassVar[str] = "betterstack"
    NAME: ClassVar[str] = "Better Stack"
    SHORT_NAME: ClassVar[str] = "Better Stack"
    LOGO_PATH: ClassVar[str] = "/statuspage_monitor/logos/betterstack.svg"
    SUPPORTS_INCIDENT_BODY: ClassVar[bool] = False

    @classmethod
    async def detect(
        cls,
        session: aiohttp.ClientSession,
        url: str,
        timeout: int,
    ) -> bool:
        """Return True if url is a Better Stack status page."""
        api_url = f"{url}{_INDEX_PATH}"
        try:
            async with asyncio.timeout(timeout):
                async with session.get(api_url, headers=_HEADERS) as resp:
                    if resp.status != 200:
                        _LOGGER.debug(
                            "Better Stack detect: %s returned HTTP %s",
                            api_url,
                            resp.status,
                        )
                        return False
                    data = await resp.json(content_type=None)
                    return data.get("data", {}).get("type") == "status_page"
        except (asyncio.TimeoutError, aiohttp.ClientError, ValueError, KeyError) as err:
            _LOGGER.debug(
                "Better Stack detect: exception fetching %s: %s: %s",
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
        *,
        meta: dict[str, str] | None = None,
    ) -> StatusPageData:
        """Fetch /index.json and return a normalised StatusPageData."""
        async with asyncio.timeout(timeout):
            async with session.get(f"{url}{_INDEX_PATH}", headers=_HEADERS) as resp:
                resp.raise_for_status()
                payload = await resp.json(content_type=None)
        return cls._parse(payload, url)

    @classmethod
    def _parse(cls, payload: dict, url: str) -> StatusPageData:
        """Map raw Better Stack JSON:API payload to StatusPageData."""
        data = payload.get("data") or {}
        attrs = data.get("attributes") or {}
        included = payload.get("included") or []

        sections: dict[str, dict] = {}
        resources: list[dict] = []
        reports: list[dict] = []
        for item in included:
            item_type = item.get("type")
            item_id = str(item.get("id", ""))
            if not item_id:
                continue
            if item_type == "status_page_section":
                sections[item_id] = item.get("attributes") or {}
            elif item_type == "status_page_resource":
                resources.append(item)
            elif item_type == "status_report":
                reports.append(item)

        components = cls._build_components(sections, resources)
        incidents, maintenances = cls._build_reports(reports, url)

        return StatusPageData(
            page=PageInfo(
                name=attrs.get("company_name") or url,
                url=url,
                updated_at=attrs.get("updated_at"),
            ),
            status=OverallStatus(
                indicator=_STATUS_MAP.get(attrs.get("aggregate_state", ""), "none"),
                description=attrs.get("announcement") or None,
            ),
            incidents=incidents,
            scheduled_maintenances=maintenances,
            components=components,
        )

    @staticmethod
    def _build_components(
        sections: dict[str, dict],
        resources: list[dict],
    ) -> list[Component]:
        """Construct Component list. Sections become group headers."""
        components: list[Component] = []

        # Section headers: only emit a header for sections that have at least one
        # child resource — empty sections add noise without value.
        used_sections: set[str] = {
            str(r.get("attributes", {}).get("status_page_section_id"))
            for r in resources
            if r.get("attributes", {}).get("status_page_section_id") is not None
        }

        for section_id, section_attrs in sections.items():
            if section_id not in used_sections:
                continue
            components.append(
                Component(
                    id=section_id,
                    name=section_attrs.get("name") or section_id,
                    status="operational",
                    group=True,
                )
            )

        for res in resources:
            res_id = str(res.get("id", ""))
            if not res_id:
                continue
            res_attrs = res.get("attributes") or {}
            section_id = res_attrs.get("status_page_section_id")
            group_id = str(section_id) if section_id is not None else None
            components.append(
                Component(
                    id=res_id,
                    name=res_attrs.get("public_name") or res_id,
                    status=_COMPONENT_STATUS_MAP.get(
                        res_attrs.get("status", ""), "operational"
                    ),
                    description=res_attrs.get("explanation") or None,
                    group=False,
                    group_id=group_id,
                )
            )

        return components

    @classmethod
    def _build_reports(
        cls,
        reports: list[dict],
        url: str,
    ) -> tuple[list[Incident], list[Maintenance]]:
        """Split status_reports into active incidents and maintenance windows."""
        now = datetime.now(timezone.utc)
        incidents: list[Incident] = []
        maintenances: list[Maintenance] = []

        for report in reports:
            report_id = str(report.get("id", ""))
            attrs = report.get("attributes") or {}
            if not report_id:
                continue
            report_type = attrs.get("report_type")
            state = attrs.get("aggregate_state", "")

            if report_type == "manual":
                if state in _RESOLVED_REPORT_STATES:
                    continue
                incidents.append(
                    Incident(
                        id=report_id,
                        name=attrs.get("title", ""),
                        status=state or "investigating",
                        impact=cls._incident_impact(attrs.get("affected_resources") or []),
                        started_at=attrs.get("starts_at"),
                        updated_at=attrs.get("starts_at"),
                    )
                )
            elif report_type == "maintenance":
                status, skip = cls._maintenance_status(attrs, now)
                if skip:
                    continue
                maintenances.append(
                    Maintenance(
                        id=report_id,
                        name=attrs.get("title", ""),
                        status=status,
                        impact="none",
                        scheduled_for=attrs.get("starts_at"),
                        scheduled_until=attrs.get("ends_at"),
                    )
                )

        return incidents, maintenances

    @staticmethod
    def _incident_impact(affected: list[dict]) -> str:
        """Derive incident impact from the worst affected resource status."""
        severities = {"downtime": 3, "degraded": 1, "maintenance": 0, "operational": 0}
        worst = max(
            (severities.get(r.get("status", ""), 0) for r in affected),
            default=0,
        )
        if worst >= 3:
            return "major"
        if worst >= 1:
            return "minor"
        return "minor"

    @staticmethod
    def _maintenance_status(
        attrs: dict,
        now: datetime,
    ) -> tuple[str, bool]:
        """Return (status, skip) for a maintenance report.

        skip=True means the maintenance is already completed and should be
        filtered out.
        """
        starts_at = _parse_dt(attrs.get("starts_at"))
        ends_at = _parse_dt(attrs.get("ends_at"))

        if ends_at is not None and ends_at < now:
            return "completed", True
        if starts_at is not None and starts_at > now:
            return "scheduled", False
        return "in_progress", False


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
