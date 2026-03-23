"""Tests for the Status.io provider."""
from __future__ import annotations

import pytest

from custom_components.statuspage_monitor.providers.status_io import (
    StatusIoProvider,
    _fetch_page_html,
    _hostname_name,
)

from .conftest import MockResponse, MockSession

URL = "https://status.example.com"
PAGE_ID = "52cbb6a6e746d36b13000116"
API_URL = f"https://api.status.io/1.0/status/{PAGE_ID}"

PAGE_HTML = f"""
<html>
<head><title>Example – Status</title></head>
<body>
<script>var statuspageId = '{PAGE_ID}';</script>
</body>
</html>
"""

API_JSON = {
    "result": {
        "status_overall": {
            "updated": "2026-03-20T12:00:00Z",
            "status": "Degraded Performance",
            "status_code": 300,
        },
        "status": [
            {
                "id": "grp1",
                "name": "API Servers",
                "status_code": 300,
                "updated": "2026-03-20T12:00:00Z",
            },
            {
                "id": "grp2",
                "name": "Web Servers",
                "status_code": 100,
                "updated": "2026-03-20T11:00:00Z",
            },
        ],
        "incidents": [
            {
                "_id": "inc1",
                "name": "Elevated latency",
                "status_code": 100,
                "datetime_open": "2026-03-20T11:00:00Z",
                "messages": [
                    {"details": "Investigating the issue.", "datetime": "2026-03-20T11:30:00Z"},
                ],
            },
            {
                "_id": "inc2",
                "name": "Resolved incident",
                "status_code": 400,
                "datetime_open": "2026-03-19T10:00:00Z",
            },
        ],
        "maintenance": {
            "active": [
                {
                    "_id": "mnt1",
                    "name": "DB upgrade",
                    "datetime_planned_start": "2026-03-20T02:00:00Z",
                    "datetime_planned_end": "2026-03-20T04:00:00Z",
                },
            ],
            "upcoming": [
                {
                    "_id": "mnt2",
                    "name": "Network maintenance",
                    "datetime_planned_start": "2026-03-25T02:00:00Z",
                    "datetime_planned_end": "2026-03-25T04:00:00Z",
                },
            ],
        },
    },
}


# -- Helper functions ---------------------------------------------------------

def test_hostname_name_strips_prefix():
    assert _hostname_name("https://status.example.com") == "example.com"
    assert _hostname_name("https://statuspage.example.com") == "example.com"
    assert _hostname_name("https://www.example.com") == "example.com"
    assert _hostname_name("https://custom.example.com") == "custom.example.com"


# -- detect() ----------------------------------------------------------------

@pytest.mark.asyncio
async def test_detect_valid():
    session = MockSession({
        URL: MockResponse(text=PAGE_HTML),
        API_URL: MockResponse(API_JSON),
    })
    assert await StatusIoProvider.detect(session, URL, 10) is True


@pytest.mark.asyncio
async def test_detect_no_page_id_in_html():
    session = MockSession({
        URL: MockResponse(text="<html><body>No page id</body></html>"),
    })
    assert await StatusIoProvider.detect(session, URL, 10) is False


@pytest.mark.asyncio
async def test_detect_api_returns_no_result():
    session = MockSession({
        URL: MockResponse(text=PAGE_HTML),
        API_URL: MockResponse({"error": "not found"}),
    })
    assert await StatusIoProvider.detect(session, URL, 10) is False


# -- fetch() ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fetch_returns_data():
    session = MockSession({
        URL: MockResponse(text=PAGE_HTML),
        API_URL: MockResponse(API_JSON),
    })
    data = await StatusIoProvider.fetch(session, URL, 10)

    assert data.page.name == "Example"
    assert data.status.indicator == "minor"

    # Resolved incidents (status_code 400) are filtered out.
    assert len(data.incidents) == 1
    assert data.incidents[0].name == "Elevated latency"
    assert data.incidents[0].body == "Investigating the issue."

    assert len(data.scheduled_maintenances) == 2
    assert len(data.components) == 2

    # provider_meta should contain the page_id for caching.
    assert data.provider_meta is not None
    assert data.provider_meta["page_id"] == PAGE_ID


@pytest.mark.asyncio
async def test_fetch_with_cached_meta():
    """When meta is provided, HTML fetch should be skipped."""
    session = MockSession({
        # No HTML endpoint registered — would fail if fetched.
        API_URL: MockResponse(API_JSON),
    })
    meta = {"page_id": PAGE_ID, "page_name": "Cached Name"}
    data = await StatusIoProvider.fetch(session, URL, 10, meta=meta)

    assert data.page.name == "Cached Name"
    assert data.status.indicator == "minor"


@pytest.mark.asyncio
async def test_fetch_no_page_id_raises():
    session = MockSession({
        URL: MockResponse(text="<html>no id</html>"),
    })
    with pytest.raises(ValueError, match="page_id"):
        await StatusIoProvider.fetch(session, URL, 10)


# -- _fetch_page_html() -------------------------------------------------------

@pytest.mark.asyncio
async def test_fetch_page_html_extracts_title():
    session = MockSession({URL: MockResponse(text=PAGE_HTML)})
    page_id, page_name = await _fetch_page_html(session, URL, 10)
    assert page_id == PAGE_ID
    assert page_name == "Example"  # " — Status" suffix stripped


@pytest.mark.asyncio
async def test_fetch_page_html_http_error():
    session = MockSession({URL: MockResponse(status=500)})
    page_id, page_name = await _fetch_page_html(session, URL, 10)
    assert page_id is None
    assert page_name is None
