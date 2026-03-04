"""Provider stub for Cachet (https://cachethq.io).

Cachet is an open-source, self-hosted status page system.  Each installation
runs on the operator's own infrastructure and exposes a REST API under
``/api/v1/`` (v2) or ``/api/`` (v3).

Detection strategy
------------------
GET {url}/api/v1/ping

- Returns ``{"data": "Pong!"}`` on Cachet v2 installations.
- If that fails, try ``GET {url}/api/ping`` for Cachet v3.
- No authentication is required for public read endpoints.

API endpoints (no authentication required)
-------------------------------------------
Cachet v2:

- Ping:        GET {url}/api/v1/ping
- Components:  GET {url}/api/v1/components?per_page=100
- Incidents:   GET {url}/api/v1/incidents?per_page=50
- Schedules:   GET {url}/api/v1/schedules?per_page=50   (v2.4+)

Cachet v3 uses the same paths without ``/v1``:

- Ping:        GET {url}/api/ping
- Components:  GET {url}/api/components?per_page=100
- Incidents:   GET {url}/api/incidents?per_page=50

Response format — Cachet v2 (flat)
------------------------------------
::

    {
      "data": [
        {
          "id": 1,
          "name": "API",
          "description": "REST endpoints",
          "status": 1,             # integer, see mapping below
          "group_id": 0,
          "updated_at": "2024-01-15T10:00:00+00:00"
        }
      ],
      "meta": {
        "pagination": { "total": 5, "current_page": 1, "per_page": 15 }
      }
    }

Response format — Cachet v3 (JSON:API)
----------------------------------------
::

    {
      "data": [
        {
          "id": "1",
          "type": "components",
          "attributes": {
            "name": "API",
            "description": "REST endpoints",
            "status": { "value": 1, "human": "Operational" },
            "group": { "id": 1, "name": "Core" },
            "updated_at": "2024-01-15T10:00:00+00:00"
          }
        }
      ]
    }

Status mapping — components
-----------------------------
Component ``status`` field is an integer (may also be a string — always cast).

    ===== =========================== =========================
    Code  Cachet meaning              Normalised
    ===== =========================== =========================
    0     Unknown                     operational (fallback)
    1     Operational                 operational
    2     Performance Issues          degraded_performance
    3     Partial Outage              partial_outage
    4     Major Outage                major_outage
    ===== =========================== =========================

Status mapping — incidents
---------------------------
    ===== ===================== ========
    Code  Cachet meaning        Active?
    ===== ===================== ========
    0     Scheduled             no
    1     Investigating         yes
    2     Identified            yes
    3     Watching              yes
    4     Fixed                 no
    ===== ===================== ========

Status mapping — schedules
---------------------------
    ===== ==================== ========
    Code  Cachet meaning       Active?
    ===== ==================== ========
    0     Upcoming             yes
    1     In Progress          yes
    2     Complete             no
    ===== ==================== ========

Overall status
--------------
Cachet has no top-level "overall status" field.  Derive it from the worst
component status:

    component 4 (major_outage)        → indicator "critical"
    component 3 (partial_outage)      → indicator "major"
    component 2 (degraded_performance)→ indicator "minor"
    all components operational/unknown→ indicator "none"

Field differences vs Atlassian Statuspage
------------------------------------------
- No explicit overall status field (derived from components)
- ``status`` may be int or str — always ``int(status)``
- Incident body: available as ``message`` field (first/only body — no update history)
- Scheduled maintenance: ``scheduled_for`` / ``scheduled_until`` fields available
- Page updated_at: not available

TODO: implement this provider
------------------------------
1. Implement ``detect``:
   - Try GET {url}/api/v1/ping; on 200 + ``data == "Pong!"`` → v2 detected
   - Try GET {url}/api/ping; on 200 + ``data == "Pong!"`` → v3 detected
   - Store detected API prefix (``/api/v1`` or ``/api``) for use in ``fetch``

2. Implement ``fetch``:
   - Use ``asyncio.gather`` to call all endpoints in parallel:
       a. GET {api_prefix}/components?per_page=100
       b. GET {api_prefix}/incidents?per_page=50
       c. GET {api_prefix}/schedules?per_page=50  (wrap in try/except; not all versions support this)
   - Implement ``_extract_attrs(item)`` helper that normalises v2 flat items
     and v3 JSON:API items to a plain dict (check for ``"attributes"`` key)
   - Always cast ``status`` to int: ``int(attrs.get("status", 0))``
   - Derive overall indicator from worst component status
   - Filter incidents: keep only those with status in {1, 2, 3}
   - Filter schedules: keep only those with status in {0, 1}

3. Handle pagination:
   - Check ``meta.pagination.total`` against ``meta.pagination.per_page``
   - For simplicity, a high ``per_page`` (100 components, 50 incidents) covers
     most self-hosted installations; full pagination is optional

4. Register provider:
   - Add ``CachetProvider`` to ``PROVIDERS`` in ``providers/__init__.py``
   - Add ``PROVIDER_CACHET`` import in ``providers/__init__.py``
"""
from __future__ import annotations

from typing import ClassVar

import aiohttp

from .base import StatusPageData


class CachetProvider:
    """Provider for the Cachet open-source status page platform (not yet implemented)."""

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
        raise NotImplementedError("Cachet provider is not yet implemented")

    @classmethod
    async def fetch(
        cls,
        session: aiohttp.ClientSession,
        url: str,
        timeout: int,
    ) -> StatusPageData:
        raise NotImplementedError("Cachet provider is not yet implemented")
