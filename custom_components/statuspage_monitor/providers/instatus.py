"""Provider stub for Instatus (https://instatus.com).

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

summary.json structure
-----------------------
::

    {
      "page": {
        "id": "abc123",
        "name": "My Service",
        "url": "https://status.myservice.com",
        "status": "UP"           # UP | HASISSUES | UNDERMAINTENANCE
      },
      "activeIncidents": [
        {
          "id": "inc_xyz",
          "name": "API degradation",
          "started": "2024-01-15T10:00:00.000Z",
          "status": "INVESTIGATING",   # INVESTIGATING | IDENTIFIED | MONITORING | RESOLVED
          "impact": "MAJOROUTAGE",     # OPERATIONAL | MINOROUTAGE | MAJOROUTAGE | PARTIALOUTAGE
          "url": "https://status.myservice.com/incidents/inc_xyz"
          # NOTE: no body/update-text available in the summary endpoint
        }
      ],
      "activeMaintenances": [
        {
          "id": "mnt_abc",
          "name": "Database migration",
          "start": "2024-01-20T02:00:00.000Z",
          "duration": 120,             # minutes; no explicit end time in API
          "status": "NOTSTARTEDYET",   # NOTSTARTEDYET | INPROGRESS | COMPLETED
          "url": "https://status.myservice.com/maintenances/mnt_abc"
        }
      ]
    }

v2/components.json structure
------------------------------
::

    {
      "page": { "id": "...", "name": "...", "url": "..." },
      "components": [
        {
          "id": "comp_abc",
          "name": "API",
          "description": "REST API endpoints",
          "status": "OPERATIONAL",     # see mapping below
          "group": null,               # null or { "id": "...", "name": "..." }
          "showUptime": true
        }
      ]
    }

Status mapping
--------------
Overall page status (page.status → indicator):

    ============= ================
    Instatus      Normalised
    ============= ================
    UP            none
    HASISSUES     major
    UNDERMAINTENANCE none  (maintenances tracked separately)
    ============= ================

Component status (component.status → Component.status):

    ===================== =========================
    Instatus              Normalised
    ===================== =========================
    OPERATIONAL           operational
    DEGRADEDPERFORMANCE   degraded_performance
    PARTIALOUTAGE         partial_outage
    MAJOROUTAGE           major_outage
    UNDERMAINTENANCE      under_maintenance
    ===================== =========================

Field differences vs Atlassian Statuspage
------------------------------------------
- Incident start time: ``started`` (not ``started_at``)
- Incident link:       ``url`` (not ``shortlink``)
- Maintenance start:   ``start`` (not ``scheduled_for``)
- Maintenance end:     not available — derive from ``start + duration``
- Incident body:       NOT available in the public summary API
                       → skip ``active_incident_description`` sensor for this provider
- Page updated_at:     not available in summary

TODO: implement this provider
------------------------------
1. Implement ``detect``:
   - GET {url}/summary.json, expect 200
   - Verify ``data.get("page", {}).get("status") in {"UP", "HASISSUES", "UNDERMAINTENANCE"}``
   - Verify ``"components"`` is NOT a root-level key (distinguishes from Atlassian)

2. Implement ``fetch``:
   - Use ``asyncio.gather`` to call both endpoints in parallel:
       a. GET {url}/summary.json
       b. GET {url}/v2/components.json
   - Map ``page.status`` to OverallStatus.indicator (see table above)
   - Map ``activeIncidents`` → list[Incident] (use ``started``, ``url`` fields)
   - Map ``activeMaintenances`` → list[Maintenance] (derive end from start+duration)
   - Map ``components`` from components endpoint → list[Component]
   - ``activeIncidents`` / ``activeMaintenances`` may be absent when empty — use
     ``.get("activeIncidents") or []``

3. Skip ``active_incident_description`` sensor:
   - Instatus does not expose incident update bodies in the public API.
   - Set a class-level flag ``SUPPORTS_INCIDENT_BODY: ClassVar[bool] = False``
     so sensor.py can skip creating the sensor for this provider.

4. Register provider:
   - Add ``InstatusProvider`` to ``PROVIDERS`` in ``providers/__init__.py``
   - Add ``PROVIDER_INSTATUS`` import in ``providers/__init__.py``
"""
from __future__ import annotations

from typing import ClassVar

import aiohttp

from .base import StatusPageData


class InstatusProvider:
    """Provider for the Instatus platform (not yet implemented)."""

    ID: ClassVar[str] = "instatus"
    NAME: ClassVar[str] = "Instatus"
    SHORT_NAME: ClassVar[str] = "Instatus"
    SUPPORTS_INCIDENT_BODY: ClassVar[bool] = False

    @classmethod
    async def detect(
        cls,
        session: aiohttp.ClientSession,
        url: str,
        timeout: int,
    ) -> bool:
        raise NotImplementedError("Instatus provider is not yet implemented")

    @classmethod
    async def fetch(
        cls,
        session: aiohttp.ClientSession,
        url: str,
        timeout: int,
    ) -> StatusPageData:
        raise NotImplementedError("Instatus provider is not yet implemented")
