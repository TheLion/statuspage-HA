"""Tests for the Cachet provider."""
from __future__ import annotations

import pytest

from custom_components.statuspage_monitor.providers.cachet import (
    CachetProvider,
    _extract_attrs,
    _get_api_prefix,
    _hostname_name,
)

from .conftest import MockResponse, MockSession

URL = "https://status.example.com"
PING_V2 = f"{URL}/api/v1/ping"
PING_V3 = f"{URL}/api/ping"
COMPONENTS_V2 = f"{URL}/api/v1/components"
INCIDENTS_V2 = f"{URL}/api/v1/incidents"
SCHEDULES_V2 = f"{URL}/api/v1/schedules"

PONG = {"data": "Pong!"}

COMPONENTS_JSON = {
    "data": [
        {
            "id": 1,
            "name": "API",
            "description": "Core API",
            "status": 1,
            "group_id": 0,
            "enabled": True,
            "updated_at": "2026-03-20 12:00:00",
        },
        {
            "id": 2,
            "name": "Dashboard",
            "description": None,
            "status": 3,
            "group_id": 0,
            "updated_at": "2026-03-20 12:00:00",
        },
    ],
}

INCIDENTS_JSON = {
    "data": [
        {
            "id": 1,
            "name": "API issues",
            "message": "Investigating API errors",
            "status": 1,
            "is_resolved": False,
            "latest_status": 1,
            "occurred_at": "2026-03-20T11:00:00Z",
            "updated_at": "2026-03-20T11:30:00Z",
            "permalink": "https://status.example.com/incidents/1",
        },
        {
            "id": 2,
            "name": "Old resolved",
            "is_resolved": True,
            "latest_status": 4,
        },
    ],
}

SCHEDULES_JSON = {
    "data": [
        {
            "id": 1,
            "name": "Planned upgrade",
            "message": "Upgrading DB",
            "status": 0,
            "scheduled_at": "2026-03-25T02:00:00Z",
            "completed_at": None,
        },
        {
            "id": 2,
            "name": "Done maintenance",
            "status": 2,
        },
    ],
}


# -- Helper functions ---------------------------------------------------------

def test_hostname_name():
    assert _hostname_name("https://status.example.com") == "example.com"


def test_extract_attrs_v2():
    """v2 items are returned as-is."""
    item = {"id": 1, "name": "API", "status": 1}
    assert _extract_attrs(item) == item


def test_extract_attrs_v3():
    """v3 JSON:API items are unwrapped from 'attributes'."""
    item = {
        "id": "1",
        "type": "components",
        "attributes": {
            "name": "Website",
            "status": {"value": 2, "human": "Performance Issues"},
            "updated": {"human": "5 min ago", "string": "2026-03-20 12:00:00"},
        },
    }
    result = _extract_attrs(item)
    assert result["id"] == "1"
    assert result["name"] == "Website"
    assert result["status"] == 2
    assert result["updated_at"] == "2026-03-20 12:00:00"


# -- _get_api_prefix() -------------------------------------------------------

@pytest.mark.asyncio
async def test_get_api_prefix_v2():
    session = MockSession({PING_V2: MockResponse(PONG)})
    assert await _get_api_prefix(session, URL, 10) == "/api/v1"


@pytest.mark.asyncio
async def test_get_api_prefix_v3():
    session = MockSession({
        PING_V2: MockResponse(status=404),
        PING_V3: MockResponse(PONG),
    })
    assert await _get_api_prefix(session, URL, 10) == "/api"


@pytest.mark.asyncio
async def test_get_api_prefix_none():
    session = MockSession({})
    assert await _get_api_prefix(session, URL, 10) is None


# -- detect() ----------------------------------------------------------------

@pytest.mark.asyncio
async def test_detect_valid():
    session = MockSession({PING_V2: MockResponse(PONG)})
    assert await CachetProvider.detect(session, URL, 10) is True


@pytest.mark.asyncio
async def test_detect_invalid():
    session = MockSession({})
    assert await CachetProvider.detect(session, URL, 10) is False


# -- fetch() ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fetch_v2():
    session = MockSession({
        PING_V2: MockResponse(PONG),
        COMPONENTS_V2: MockResponse(COMPONENTS_JSON),
        INCIDENTS_V2: MockResponse(INCIDENTS_JSON),
        SCHEDULES_V2: MockResponse(SCHEDULES_JSON),
    })
    data = await CachetProvider.fetch(session, URL, 10)

    assert data.page.name == "example.com"
    # Worst component status is 3 (partial_outage) → major.
    assert data.status.indicator == "major"

    assert len(data.components) == 2
    assert data.components[0].status == "operational"
    assert data.components[1].status == "partial_outage"

    # Resolved incidents are filtered.
    assert len(data.incidents) == 1
    assert data.incidents[0].name == "API issues"
    assert data.incidents[0].body == "Investigating API errors"

    # Completed schedules are filtered.
    assert len(data.scheduled_maintenances) == 1
    assert data.scheduled_maintenances[0].name == "Planned upgrade"

    # provider_meta for caching.
    assert data.provider_meta == {"api_prefix": "/api/v1"}


@pytest.mark.asyncio
async def test_fetch_with_cached_meta():
    """When meta is provided, ping probe should be skipped."""
    session = MockSession({
        # No ping endpoint — would fail if probed.
        COMPONENTS_V2: MockResponse(COMPONENTS_JSON),
        INCIDENTS_V2: MockResponse(INCIDENTS_JSON),
        SCHEDULES_V2: MockResponse(SCHEDULES_JSON),
    })
    meta = {"api_prefix": "/api/v1"}
    data = await CachetProvider.fetch(session, URL, 10, meta=meta)

    assert data.status.indicator == "major"
    assert len(data.components) == 2


@pytest.mark.asyncio
async def test_fetch_no_prefix_raises():
    session = MockSession({})
    with pytest.raises(ValueError, match="not reachable"):
        await CachetProvider.fetch(session, URL, 10)
