"""Tests for the UptimeRobot provider."""
from __future__ import annotations

import pytest

from custom_components.statuspage_monitor.providers.uptimerobot import (
    UptimeRobotProvider,
    _fetch_page_info,
    _hostname_name,
)

from .conftest import MockResponse, MockSession

URL = "https://stats.example.com"
API_PATH = "https://status.uptimerobot.com/api/getMonitorList/abc123"
EVENTS_PATH = "https://status.uptimerobot.com/api/getEventFeed/abc123"

PAGE_HTML = f"""
<html>
<head><title>Example Status Page</title></head>
<body>
<script>
window.pspApiPath = '{API_PATH}';
window.eventsApiPath = '{EVENTS_PATH}';
</script>
</body>
</html>
"""

MONITORS_JSON = {
    "status": "ok",
    "data": [
        {
            "monitorId": 111,
            "name": "API",
            "statusClass": "success",
            "groupId": 0,
        },
        {
            "monitorId": 222,
            "name": "Website",
            "statusClass": "danger",
            "groupId": 0,
        },
    ],
}

EVENTS_JSON = {
    "status": True,
    "results": [
        {
            "type": "incident",
            "id": 1001,
            "title": "Website down",
            "content": "Investigating downtime.",
            "date": "Mar 20, 2026",
            "time": "11:00",
            "status": 0,
        },
        {
            "type": "maintenance",
            "id": 1002,
            "title": "Server upgrade",
            "date": "Mar 25, 2026",
            "time": "02:00",
            "status": 0,
        },
        {
            "type": "incident",
            "id": 1003,
            "title": "Resolved issue",
            "status": 2,
        },
    ],
}


# -- Helper functions ---------------------------------------------------------

def test_hostname_name_strips_prefix():
    assert _hostname_name("https://status.example.com") == "example.com"
    assert _hostname_name("https://stats.example.com") == "example.com"


# -- detect() ----------------------------------------------------------------

@pytest.mark.asyncio
async def test_detect_valid():
    session = MockSession({URL: MockResponse(text=PAGE_HTML)})
    assert await UptimeRobotProvider.detect(session, URL, 10) is True


@pytest.mark.asyncio
async def test_detect_no_api_path():
    session = MockSession({URL: MockResponse(text="<html>nothing</html>")})
    assert await UptimeRobotProvider.detect(session, URL, 10) is False


# -- fetch() ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fetch_returns_data():
    session = MockSession({
        URL: MockResponse(text=PAGE_HTML),
        API_PATH: MockResponse(MONITORS_JSON),
        EVENTS_PATH: MockResponse(EVENTS_JSON),
    })
    data = await UptimeRobotProvider.fetch(session, URL, 10)

    assert data.page.name == "Example"  # " Status Page" suffix stripped
    # Worst monitor is "danger" → major.
    assert data.status.indicator == "major"

    assert len(data.components) == 2
    assert data.components[0].status == "operational"
    assert data.components[1].status == "major_outage"

    # Resolved events (status 2) are filtered.
    assert len(data.incidents) == 1
    assert data.incidents[0].name == "Website down"
    assert data.incidents[0].body == "Investigating downtime."

    assert len(data.scheduled_maintenances) == 1

    # provider_meta should be populated for caching.
    assert data.provider_meta is not None
    assert data.provider_meta["api_path"] == API_PATH
    assert data.provider_meta["events_path"] == EVENTS_PATH


@pytest.mark.asyncio
async def test_fetch_with_cached_meta():
    """When meta is provided, HTML fetch should be skipped."""
    session = MockSession({
        # No HTML endpoint — would fail if fetched.
        API_PATH: MockResponse(MONITORS_JSON),
        EVENTS_PATH: MockResponse(EVENTS_JSON),
    })
    meta = {"api_path": API_PATH, "events_path": EVENTS_PATH, "page_name": "Cached"}
    data = await UptimeRobotProvider.fetch(session, URL, 10, meta=meta)

    assert data.page.name == "Cached"
    assert len(data.components) == 2


@pytest.mark.asyncio
async def test_fetch_no_api_path_raises():
    session = MockSession({URL: MockResponse(text="<html>no api</html>")})
    with pytest.raises(ValueError, match="API path"):
        await UptimeRobotProvider.fetch(session, URL, 10)
