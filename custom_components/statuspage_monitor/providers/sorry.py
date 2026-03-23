"""Provider implementation for Sorry™ (https://www.sorryapp.com).

Sorry™ is a hosted status-page platform used by services like Moneybird,
Broadcom, Pingdom, and many others.

Detection strategy
------------------
GET {url}/api/v1/

- Returns HTTP 200 with a ``"page"`` object containing ``"state"`` and
  ``"links"`` with ``"components"`` and ``"notices"`` sub-keys.

API endpoints (no authentication required)
-------------------------------------------
- Page info:   GET {url}/api/v1/
- Components:  GET {url}/api/v1/components  (max 25/page, meta.next_page)
- Notices:     GET {url}/api/v1/notices     (max 25/page, meta.next_page)
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

_API_ROOT = "/api/v1/"
_COMPONENTS_PATH = "/api/v1/components"
_NOTICES_PATH = "/api/v1/notices"
_HEADERS = {"Accept": "application/json"}

# page.state → OverallStatus.indicator
# Sorry has no minor/major/critical distinction — everything maps to "minor"
_STATUS_MAP: dict[str, str] = {
    "operational": "none",
    "degraded": "minor",
    "maintenance": "minor",
}

# component.state → Component.status
_COMPONENT_STATUS_MAP: dict[str, str] = {
    "operational": "operational",
    "degraded": "partial_outage",
    "partially-degraded": "degraded_performance",
}

# notice.state values that indicate an active incident
_ACTIVE_INCIDENT_STATES = {"investigating", "identified"}

# notice.state values that indicate an active maintenance
_ACTIVE_MAINTENANCE_STATES = {"scheduled", "underway"}


class SorryProvider:
    """Provider for the Sorry™ platform (sorryapp.com)."""

    ID: ClassVar[str] = "sorry"
    NAME: ClassVar[str] = "Sorry™"
    SHORT_NAME: ClassVar[str] = "Sorry"
    LOGO_PATH: ClassVar[str] = "/statuspage_monitor/logos/sorry.svg"
    SUPPORTS_INCIDENT_BODY: ClassVar[bool] = True

    @classmethod
    async def detect(
        cls,
        session: aiohttp.ClientSession,
        url: str,
        timeout: int,
    ) -> bool:
        """Return True if url is a Sorry™ status page."""
        api_url = f"{url}{_API_ROOT}"
        try:
            async with asyncio.timeout(timeout):
                async with session.get(api_url, headers=_HEADERS) as resp:
                    if resp.status != 200:
                        _LOGGER.debug(
                            "Sorry detect: %s returned HTTP %s", api_url, resp.status
                        )
                        return False
                    data = await resp.json(content_type=None)
                    page = data.get("page", {})
                    if not page.get("state"):
                        return False
                    links = page.get("links", {})
                    return bool(links.get("components") and links.get("notices"))
        except (asyncio.TimeoutError, aiohttp.ClientError, ValueError, KeyError) as err:
            _LOGGER.debug(
                "Sorry detect: exception fetching %s: %s: %s",
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
        """Fetch page info, components, and active notices in parallel."""
        notices_url = f"{url}{_NOTICES_PATH}?timeline_state=present"
        async with asyncio.timeout(timeout):
            root, components, notices = await asyncio.gather(
                cls._get_json(session, f"{url}{_API_ROOT}"),
                cls._get_all_pages(session, url, f"{url}{_COMPONENTS_PATH}", "components"),
                cls._get_all_pages(session, url, notices_url, "notices"),
            )
        return cls._parse(
            root,
            {"components": components},
            {"notices": notices},
            url,
        )

    @classmethod
    async def _get_json(cls, session: aiohttp.ClientSession, url: str) -> dict:
        async with session.get(url, headers=_HEADERS) as resp:
            resp.raise_for_status()
            return await resp.json(content_type=None)

    @classmethod
    async def _get_all_pages(
        cls, session: aiohttp.ClientSession, base_url: str, url: str, key: str
    ) -> list[dict]:
        """Fetch all pages of a paginated Sorry™ endpoint."""
        items: list[dict] = []
        next_url: str | None = url
        while next_url:
            # next_page from the API can be a relative path.
            if next_url.startswith("/"):
                next_url = f"{base_url}{next_url}"
            data = await cls._get_json(session, next_url)
            items.extend(data.get(key, []))
            next_url = (data.get("meta") or {}).get("next_page")
        return items

    @classmethod
    def _parse(
        cls,
        root: dict,
        comp_raw: dict,
        notices_raw: dict,
        url: str,
    ) -> StatusPageData:
        """Map raw Sorry™ JSON to the normalised StatusPageData model."""
        page = root.get("page", {})
        page_state = page.get("state", "operational")

        components_list = comp_raw.get("components", [])

        # Determine which component IDs are group headers:
        # a component is a group header if its ID is referenced as parent_id by a child.
        parent_ids: set[str] = {
            str(c["parent_id"])
            for c in components_list
            if c.get("parent_id") is not None
        }

        incidents: list[Incident] = []
        maintenances: list[Maintenance] = []

        for notice in notices_raw.get("notices", []):
            notice_type = notice.get("type")
            state = notice.get("state", "")
            notice_id = str(notice.get("id", ""))
            name = notice.get("subject", "")
            notice_url = notice.get("url")
            latest = notice.get("latest_update") or {}
            body = latest.get("content") or None

            if notice_type == "unplanned" and state in _ACTIVE_INCIDENT_STATES:
                incidents.append(
                    Incident(
                        id=notice_id,
                        name=name,
                        status=state,
                        impact="minor",  # Sorry has no severity levels
                        shortlink=notice_url,
                        started_at=notice.get("began_at"),
                        updated_at=notice.get("updated_at"),
                        body=body,
                    )
                )
            elif notice_type == "planned" and state in _ACTIVE_MAINTENANCE_STATES:
                maintenances.append(
                    Maintenance(
                        id=notice_id,
                        name=name,
                        status=state,
                        impact="none",
                        shortlink=notice_url,
                        scheduled_for=notice.get("begins_at"),
                        scheduled_until=notice.get("ends_at"),
                    )
                )

        return StatusPageData(
            page=PageInfo(
                name=page.get("name") or url,
                url=url,
                updated_at=page.get("updated_at"),
            ),
            status=OverallStatus(
                indicator=_STATUS_MAP.get(page_state, "none"),
                description=page.get("state_text"),
            ),
            incidents=incidents,
            scheduled_maintenances=maintenances,
            components=[
                Component(
                    id=str(comp["id"]),
                    name=comp.get("name", str(comp["id"])),
                    status=_COMPONENT_STATUS_MAP.get(
                        comp.get("state", ""), "operational"
                    ),
                    description=comp.get("description") or None,
                    group=str(comp["id"]) in parent_ids,
                    group_id=(
                        str(comp["parent_id"])
                        if comp.get("parent_id") is not None
                        else None
                    ),
                )
                for comp in components_list
                if comp.get("id") is not None
            ],
        )
