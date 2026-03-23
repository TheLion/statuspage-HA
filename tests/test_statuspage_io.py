"""Tests for the Atlassian Statuspage.io provider."""
from __future__ import annotations

import pytest

from custom_components.statuspage_monitor.providers.statuspage_io import (
    StatuspageIoProvider,
)

from .conftest import MockResponse, MockSession

URL = "https://status.example.com"
API_URL = f"{URL}/api/v2/summary.json"


# -- Fixtures with realistic API data ----------------------------------------

SUMMARY_JSON = {
    "page": {
        "id": "abc123",
        "name": "Example Service",
        "url": "https://status.example.com",
        "updated_at": "2026-03-20T12:00:00Z",
    },
    "status": {
        "indicator": "minor",
        "description": "Minor System Outage",
    },
    "components": [
        {
            "id": "comp1",
            "name": "API",
            "status": "operational",
            "description": "Core API",
            "group": False,
            "group_id": None,
            "updated_at": "2026-03-20T12:00:00Z",
            "showcase": True,
        },
        {
            "id": "comp2",
            "name": "Dashboard",
            "status": "degraded_performance",
            "description": None,
            "group": False,
            "group_id": None,
        },
    ],
    "incidents": [
        {
            "id": "inc1",
            "name": "Elevated error rates",
            "status": "investigating",
            "impact": "minor",
            "shortlink": "https://stspg.io/abc",
            "started_at": "2026-03-20T11:00:00Z",
            "updated_at": "2026-03-20T11:30:00Z",
            "incident_updates": [
                {"body": "We are investigating."},
            ],
        },
        {
            "id": "inc2",
            "name": "Old resolved incident",
            "status": "resolved",
            "impact": "major",
        },
    ],
    "scheduled_maintenances": [
        {
            "id": "mnt1",
            "name": "Database migration",
            "status": "scheduled",
            "impact": "none",
            "shortlink": "https://stspg.io/mnt",
            "scheduled_for": "2026-03-25T02:00:00Z",
            "scheduled_until": "2026-03-25T04:00:00Z",
        },
    ],
}


# -- detect() ----------------------------------------------------------------

@pytest.mark.asyncio
async def test_detect_valid():
    session = MockSession({API_URL: MockResponse(SUMMARY_JSON)})
    assert await StatuspageIoProvider.detect(session, URL, 10) is True


@pytest.mark.asyncio
async def test_detect_missing_keys():
    session = MockSession({API_URL: MockResponse({"page": {}})})
    assert await StatuspageIoProvider.detect(session, URL, 10) is False


@pytest.mark.asyncio
async def test_detect_http_error():
    session = MockSession({API_URL: MockResponse(status=500)})
    assert await StatuspageIoProvider.detect(session, URL, 10) is False


@pytest.mark.asyncio
async def test_detect_connection_error():
    session = MockSession({})  # No matching URL → 404
    assert await StatuspageIoProvider.detect(session, URL, 10) is False


# -- _parse() ----------------------------------------------------------------

def test_parse_full_response():
    data = StatuspageIoProvider._parse(SUMMARY_JSON, URL)

    assert data.page.name == "Example Service"
    assert data.page.url == URL
    assert data.status.indicator == "minor"
    assert data.status.description == "Minor System Outage"

    # Resolved incidents are filtered out.
    assert len(data.incidents) == 1
    assert data.incidents[0].id == "inc1"
    assert data.incidents[0].name == "Elevated error rates"
    assert data.incidents[0].body == "We are investigating."

    assert len(data.scheduled_maintenances) == 1
    assert data.scheduled_maintenances[0].id == "mnt1"

    assert len(data.components) == 2
    assert data.components[0].status == "operational"
    assert data.components[1].status == "degraded_performance"


def test_parse_empty_response():
    data = StatuspageIoProvider._parse({}, URL)

    assert data.page.name == URL
    assert data.status.indicator == "none"
    assert data.incidents == []
    assert data.scheduled_maintenances == []
    assert data.components == []


def test_parse_unknown_indicator():
    raw = {"status": {"indicator": "banana"}, "components": [], "incidents": []}
    data = StatuspageIoProvider._parse(raw, URL)
    assert data.status.indicator == "none"


def test_parse_unknown_component_status():
    raw = {
        "components": [{"id": "c1", "name": "X", "status": "exploding"}],
    }
    data = StatuspageIoProvider._parse(raw, URL)
    assert data.components[0].status == "operational"


# -- fetch() ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fetch_returns_data():
    session = MockSession({API_URL: MockResponse(SUMMARY_JSON)})
    data = await StatuspageIoProvider.fetch(session, URL, 10)

    assert data.page.name == "Example Service"
    assert data.status.indicator == "minor"
    assert len(data.incidents) == 1


@pytest.mark.asyncio
async def test_fetch_http_error():
    session = MockSession({API_URL: MockResponse(status=503)})
    with pytest.raises(Exception):
        await StatuspageIoProvider.fetch(session, URL, 10)
