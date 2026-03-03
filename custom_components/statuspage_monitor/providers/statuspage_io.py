"""Provider implementation for Atlassian Statuspage (statuspage.io).

Covers any service that hosts its status page on the Atlassian Statuspage
platform – e.g. https://status.claude.com, https://www.githubstatus.com,
https://status.openai.com, etc.

Detection strategy
------------------
GET {url}/api/v2/summary.json and verify the response contains both
``"status"`` and ``"components"`` keys.  This endpoint is part of the
public Statuspage.io API and has been stable since v2.

API reference: https://support.atlassian.com/statuspage/docs/get-summary/
"""
from __future__ import annotations

import asyncio
import logging
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

_API_PATH = "/api/v2/summary.json"
_HEADERS = {"Accept": "application/json"}

# Canonical indicator values used internally; map any unknown value → "none"
_VALID_INDICATORS = {"none", "minor", "major", "critical"}

# Canonical component status values; map any unknown value → "operational"
_VALID_COMPONENT_STATUSES = {
    "operational",
    "degraded_performance",
    "partial_outage",
    "major_outage",
    "under_maintenance",
}


class StatuspageIoProvider:
    """Provider for the Atlassian Statuspage.io platform."""

    ID: ClassVar[str] = "statuspage_io"
    NAME: ClassVar[str] = "Atlassian Statuspage (Statuspage.io)"

    @classmethod
    async def detect(
        cls,
        session: aiohttp.ClientSession,
        url: str,
        timeout: int,
    ) -> bool:
        """Return True if the URL responds with a valid Statuspage.io summary."""
        try:
            async with asyncio.timeout(timeout):
                async with session.get(
                    f"{url}{_API_PATH}", headers=_HEADERS
                ) as resp:
                    if resp.status != 200:
                        return False
                    data = await resp.json(content_type=None)
                    return "status" in data and "components" in data
        except Exception:  # noqa: BLE001
            return False

    @classmethod
    async def fetch(
        cls,
        session: aiohttp.ClientSession,
        url: str,
        timeout: int,
    ) -> StatusPageData:
        """Fetch the summary endpoint and return normalised StatusPageData."""
        api_url = f"{url}{_API_PATH}"
        async with asyncio.timeout(timeout):
            async with session.get(api_url, headers=_HEADERS) as resp:
                resp.raise_for_status()
                raw = await resp.json(content_type=None)

        data = cls._parse(raw, url)
        _LOGGER.debug(
            "Fetched %s: indicator=%s components=%d incidents=%d maintenances=%d",
            api_url,
            data.status.indicator,
            len(data.components),
            len(data.incidents),
            len(data.scheduled_maintenances),
        )
        return data

    @classmethod
    def _parse(cls, raw: dict, url: str) -> StatusPageData:
        """Map raw Statuspage.io JSON to the normalised StatusPageData model."""
        page_raw = raw.get("page", {})
        status_raw = raw.get("status", {})

        indicator = status_raw.get("indicator", "none")
        if indicator not in _VALID_INDICATORS:
            indicator = "none"

        return StatusPageData(
            page=PageInfo(
                name=page_raw.get("name") or url,
                url=url,
                updated_at=page_raw.get("updated_at"),
            ),
            status=OverallStatus(
                indicator=indicator,
                description=status_raw.get("description"),
            ),
            incidents=[
                Incident(
                    id=inc["id"],
                    name=inc.get("name", ""),
                    status=inc.get("status", ""),
                    impact=inc.get("impact", ""),
                    shortlink=inc.get("shortlink"),
                    started_at=inc.get("started_at"),
                    updated_at=inc.get("updated_at"),
                )
                for inc in raw.get("incidents", [])
                if inc.get("status") != "resolved"
            ],
            scheduled_maintenances=[
                Maintenance(
                    id=m["id"],
                    name=m.get("name", ""),
                    status=m.get("status", ""),
                    impact=m.get("impact", ""),
                    shortlink=m.get("shortlink"),
                    scheduled_for=m.get("scheduled_for"),
                    scheduled_until=m.get("scheduled_until"),
                )
                for m in raw.get("scheduled_maintenances", [])
            ],
            components=[
                Component(
                    id=comp["id"],
                    name=comp.get("name", comp["id"]),
                    status=(
                        comp.get("status", "operational")
                        if comp.get("status") in _VALID_COMPONENT_STATUSES
                        else "operational"
                    ),
                    description=comp.get("description"),
                    group=comp.get("group", False),
                    group_id=comp.get("group_id"),
                    updated_at=comp.get("updated_at"),
                    showcase=comp.get("showcase"),
                )
                for comp in raw.get("components", [])
                if comp.get("id")
            ],
        )
