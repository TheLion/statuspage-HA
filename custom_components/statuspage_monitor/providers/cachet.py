"""Provider implementation for Cachet (https://cachethq.io).

Cachet is an open-source, self-hosted status page system.

Detection strategy
------------------
Try ``GET {url}/api/v1/ping`` (Cachet v2) then ``GET {url}/api/ping`` (v3).
Both return ``{"data": "Pong!"}`` on valid Cachet installations.

API reference — verified against demo.cachethq.io (v2) and v3.cachethq.io
---------------------------------------------------------------------------
Cachet v2  base prefix: ``/api/v1``
Cachet v3  base prefix: ``/api``

Endpoints (no authentication for public read):

  Ping:        GET {prefix}/ping
  Components:  GET {prefix}/components?per_page=100
  Incidents:   GET {prefix}/incidents?per_page=50
  Schedules:   GET {prefix}/schedules?per_page=50   (v2 only; 404 on v3)

v2 component item::

    {
      "id":          1,
      "name":        "API",
      "description": "Used by third-parties",
      "status":      1,        # integer 1–4, see mapping
      "group_id":    0,        # 0 = no group
      "updated_at":  "2026-03-04 15:30:02"
    }

v3 component item (JSON:API format)::

    {
      "id":   "1",
      "type": "components",
      "attributes": {
        "name":        "Cachet Website",
        "description": "The Cachet website.",
        "status": { "human": "Operational", "value": 1 },
        "updated": { "human": "9 minutes ago", "string": "2026-03-04 15:30:05" }
      }
    }

v2 incident item::

    {
      "id":            1,
      "name":          "Our monkeys aren't performing",
      "message":       "We're investigating...",
      "status":        1,       # 1=Investigating, 2=Identified, 3=Watching, 4=Fixed
      "occurred_at":   "2026-03-04 15:30:02",
      "updated_at":    "2026-03-04 15:30:02",
      "is_resolved":   false,
      "latest_status": 1,       # status of most recent update
      "permalink":     "https://demo.cachethq.io/incidents/1"
    }

v2 schedule item::

    {
      "id":           1,
      "name":         "Scheduled maintenance",
      "message":      "Description text",
      "status":       0,        # 0=Upcoming, 1=In Progress, 2=Complete
      "scheduled_at": "2026-03-04 17:30:02",
      "completed_at": null
    }

Status code mapping — components
----------------------------------
    ===== ========================= =======================
    Code  Cachet meaning            Normalised
    ===== ========================= =======================
    0     Unknown                   operational  (fallback)
    1     Operational               operational
    2     Performance Issues        degraded_performance
    3     Partial Outage            partial_outage
    4     Major Outage              major_outage
    ===== ========================= =======================

Overall status is derived from the worst component status:
  any 4 → "critical",  any 3 → "major",  any 2 → "minor",  else → "none".

Status mapping — incidents
---------------------------
  Active:   latest_status in {1, 2, 3}  (or is_resolved == false)
  Resolved: latest_status == 4          → skip

Status mapping — schedules
---------------------------
  Upcoming:    status 0  → include
  In Progress: status 1  → include
  Complete:    status 2  → skip
"""
from __future__ import annotations

import asyncio
import logging
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

_COMPONENT_STATUS_MAP: dict[int, str] = {
    0: "operational",
    1: "operational",
    2: "degraded_performance",
    3: "partial_outage",
    4: "major_outage",
}
_COMPONENT_STATUS_SEVERITY: dict[int, int] = {0: 0, 1: 0, 2: 1, 3: 2, 4: 3}
_SEVERITY_TO_INDICATOR = {0: "none", 1: "minor", 2: "major", 3: "critical"}

_INCIDENT_STATUS_MAP: dict[int, str] = {
    1: "investigating",
    2: "identified",
    3: "monitoring",
    4: "resolved",
}

_MAINTENANCE_STATUS_MAP: dict[int, str] = {
    0: "scheduled",
    1: "in_progress",
    2: "completed",
}


async def _json(resp_or_exc, fallback=None):
    """Read JSON from an aiohttp response, returning *fallback* on any error."""
    if isinstance(resp_or_exc, Exception) or resp_or_exc is None:
        return fallback or {}
    async with resp_or_exc as r:
        if r.status != 200:
            return fallback or {}
        return await r.json(content_type=None)


async def _get_all_pages(
    session: aiohttp.ClientSession,
    url: str,
    per_page: int = 100,
    max_pages: int = 10,
) -> list[dict]:
    """Fetch all pages of a paginated Cachet endpoint."""
    items: list[dict] = []
    for page in range(1, max_pages + 1):
        async with session.get(
            f"{url}?per_page={per_page}&page={page}", headers=_HEADERS
        ) as resp:
            if resp.status == 429:
                _LOGGER.debug("Cachet: rate limited at %s page %d, returning partial results", url, page)
                break
            if resp.status != 200:
                break
            data = await resp.json(content_type=None)
        page_items = data.get("data", [])
        if not page_items:
            break
        items.extend(page_items)
        meta = data.get("meta", {}).get("pagination", {})
        if page >= meta.get("total_pages", 1):
            break
    return items


def _hostname_name(url: str) -> str:
    host = urlparse(url).netloc
    for prefix in ("status.", "statuspage.", "www."):
        if host.startswith(prefix):
            host = host[len(prefix):]
    return host


def _extract_attrs(item: dict) -> dict:
    """Normalise v2 (flat) and v3 (JSON:API) items to a plain attribute dict.

    v3 items have an ``"attributes"`` key; all fields are inside it.  Status
    is an object ``{value, human}`` rather than a plain integer.  Date fields
    are objects ``{human, string}`` rather than plain strings.
    """
    if "attributes" not in item:
        return item
    attrs = dict(item["attributes"])
    attrs["id"] = str(item["id"])
    # Unwrap status: {value, human} → integer
    if isinstance(attrs.get("status"), dict):
        attrs["status"] = attrs["status"].get("value", 1)
    # Unwrap date objects: updated/created → *_at string
    for key in ("updated", "created"):
        val = attrs.pop(key, None)
        if isinstance(val, dict):
            attrs[f"{key}_at"] = val.get("string")
        elif val is not None:
            attrs[f"{key}_at"] = val
    return attrs


async def _get_api_prefix(
    session: aiohttp.ClientSession,
    url: str,
    timeout: int,
) -> str | None:
    """Return ``'/api/v1'`` for Cachet v2, ``'/api'`` for v3, or None."""
    for prefix in ("/api/v1", "/api"):
        try:
            async with asyncio.timeout(min(timeout, 8)):
                async with session.get(
                    f"{url}{prefix}/ping", headers=_HEADERS
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json(content_type=None)
                        if data.get("data") == "Pong!":
                            return prefix
        except (asyncio.TimeoutError, aiohttp.ClientError, ValueError, KeyError) as err:
            _LOGGER.debug(
                "Cachet: ping %s%s/ping failed: %s: %s",
                url, prefix, type(err).__name__, err,
            )
    return None


class CachetProvider:
    """Provider for the Cachet open-source status page platform."""

    ID: ClassVar[str] = "cachet"
    NAME: ClassVar[str] = "Cachet"
    SHORT_NAME: ClassVar[str] = "Cachet"
    LOGO_PATH: ClassVar[str] = "/statuspage_monitor/logos/cachet.svg"

    @classmethod
    async def detect(
        cls,
        session: aiohttp.ClientSession,
        url: str,
        timeout: int,
    ) -> bool:
        """Return True if *url* is a Cachet instance."""
        prefix = await _get_api_prefix(session, url, timeout)
        if not prefix:
            _LOGGER.debug("Cachet detect: no valid ping response from %s", url)
        return prefix is not None

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
        # Use cached metadata when available to skip the ping probe.
        if meta and meta.get("api_prefix"):
            prefix = meta["api_prefix"]
        else:
            prefix = await _get_api_prefix(session, url, timeout)
            if not prefix:
                raise ValueError(f"Cachet API not reachable at {url}")

        is_v2 = prefix == "/api/v1"

        # Fetch components, incidents, and (v2-only) schedules in parallel.
        coros = [
            _get_all_pages(session, f"{url}{prefix}/components", per_page=100),
            _get_all_pages(session, f"{url}{prefix}/incidents", per_page=50),
        ]
        if is_v2:
            coros.append(
                _get_all_pages(session, f"{url}{prefix}/schedules", per_page=50)
            )

        async with asyncio.timeout(timeout):
            results = await asyncio.gather(*coros)

        raw_components = [_extract_attrs(c) for c in results[0]]
        raw_incidents  = [_extract_attrs(i) for i in results[1]]
        raw_schedules  = [_extract_attrs(s) for s in results[2]] if is_v2 else []

        # Overall status — derived from worst component.
        worst_severity = max(
            (_COMPONENT_STATUS_SEVERITY.get(int(c.get("status", 1)), 0) for c in raw_components),
            default=0,
        )
        indicator = _SEVERITY_TO_INDICATOR.get(worst_severity, "none")

        page = PageInfo(name=_hostname_name(url), url=url)
        status = OverallStatus(indicator=indicator)

        components: list[Component] = []
        for c in raw_components:
            comp_status_int = int(c.get("status", 1))
            group_id_raw = c.get("group_id")
            components.append(Component(
                id=str(c.get("id", "")),
                name=c.get("name", ""),
                description=c.get("description") or None,
                status=_COMPONENT_STATUS_MAP.get(comp_status_int, "operational"),
                group=bool(c.get("group_id") == 0 and c.get("enabled") is True
                           and not c.get("name")),  # Cachet has no explicit group flag
                group_id=str(group_id_raw) if group_id_raw else None,
                updated_at=c.get("updated_at"),
            ))

        # Active incidents: is_resolved == false and latest_status not 4.
        incidents: list[Incident] = []
        for inc in raw_incidents:
            if inc.get("is_resolved") or int(inc.get("latest_status", 4)) == 4:
                continue
            latest_status_int = int(inc.get("latest_status") or inc.get("status", 1))
            impact = _SEVERITY_TO_INDICATOR.get(worst_severity, "minor") or "minor"
            incidents.append(Incident(
                id=str(inc.get("id", "")),
                name=inc.get("name", ""),
                status=_INCIDENT_STATUS_MAP.get(latest_status_int, "investigating"),
                impact=impact,
                shortlink=inc.get("permalink"),
                started_at=inc.get("occurred_at"),
                updated_at=inc.get("updated_at"),
                body=inc.get("message"),
            ))

        # Scheduled maintenances: upcoming (0) and in-progress (1) only.
        maintenances: list[Maintenance] = []
        for s in raw_schedules:
            sched_status = int(s.get("status", 2))
            if sched_status == 2:   # completed
                continue
            maintenances.append(Maintenance(
                id=str(s.get("id", "")),
                name=s.get("name", ""),
                status=_MAINTENANCE_STATUS_MAP.get(sched_status, "scheduled"),
                impact="none",
                scheduled_for=s.get("scheduled_at"),
                scheduled_until=s.get("completed_at"),
            ))

        return StatusPageData(
            page=page,
            status=status,
            incidents=incidents,
            scheduled_maintenances=maintenances,
            components=components,
            provider_meta={"api_prefix": prefix},
        )
