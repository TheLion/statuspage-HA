"""Provider stub for Status.io (https://status.io).

Status.io is a hosted statuspage platform that uses a different API from
Atlassian Statuspage.io.  Each status page on Status.io has a unique
``page_id`` which is required to call the REST API:

    GET https://api.status.io/1.0/status/{page_id}

The page_id is embedded in the status page HTML (typically in a ``<script>``
block as a JavaScript variable or in a ``data-`` attribute).  Detection
would require fetching and parsing the HTML to extract the page_id before
querying the API.

TODO: implement this provider
------------------------------
1. Implement ``detect``:
   - Fetch the page HTML at *url*
   - Extract the page_id (e.g. from a ``<meta name="page-id">`` tag or JS)
   - Optionally: try ``{url}/api/v1/status`` if Status.io exposes a
     JSON endpoint on the custom domain
2. Implement ``fetch``:
   - Call ``https://api.status.io/1.0/status/{page_id}``
   - Map the response fields to ``StatusPageData`` (field names differ from
     Statuspage.io – refer to the Status.io API docs)
3. Add ``StatusIoProvider`` to the ``PROVIDERS`` list in ``providers/__init__.py``
"""
from __future__ import annotations

from typing import ClassVar

import aiohttp

from .base import StatusPageData


class StatusIoProvider:
    """Provider for the Status.io platform (not yet implemented)."""

    ID: ClassVar[str] = "status_io"
    NAME: ClassVar[str] = "Status.io"

    @classmethod
    async def detect(
        cls,
        session: aiohttp.ClientSession,
        url: str,
        timeout: int,
    ) -> bool:
        raise NotImplementedError("Status.io provider is not yet implemented")

    @classmethod
    async def fetch(
        cls,
        session: aiohttp.ClientSession,
        url: str,
        timeout: int,
    ) -> StatusPageData:
        raise NotImplementedError("Status.io provider is not yet implemented")
