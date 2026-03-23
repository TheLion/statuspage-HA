"""Tests for the Sorry™ provider."""
from __future__ import annotations

import pytest

from custom_components.statuspage_monitor.providers.sorry import SorryProvider

from .conftest import MockResponse, MockSession

URL = "https://status.example.com"
API_ROOT = f"{URL}/api/v1/"
COMPONENTS_URL = f"{URL}/api/v1/components"
NOTICES_URL = f"{URL}/api/v1/notices"

ROOT_JSON = {
    "page": {
        "name": "Example",
        "state": "degraded",
        "state_text": "Some services are experiencing issues",
        "updated_at": "2026-03-20T12:00:00Z",
        "links": {
            "components": f"{COMPONENTS_URL}",
            "notices": f"{NOTICES_URL}",
        },
    },
}

COMPONENTS_JSON = {
    "components": [
        {
            "id": 1,
            "name": "API",
            "state": "operational",
            "description": "Core API",
            "parent_id": None,
        },
        {
            "id": 2,
            "name": "Web App",
            "state": "degraded",
            "description": None,
            "parent_id": 1,
        },
    ],
}

NOTICES_JSON = {
    "notices": [
        {
            "id": 101,
            "type": "unplanned",
            "state": "investigating",
            "subject": "High latency",
            "url": "https://status.example.com/notices/101",
            "began_at": "2026-03-20T11:00:00Z",
            "updated_at": "2026-03-20T11:30:00Z",
            "latest_update": {"content": "Looking into it."},
        },
        {
            "id": 102,
            "type": "planned",
            "state": "scheduled",
            "subject": "DB migration",
            "url": "https://status.example.com/notices/102",
            "begins_at": "2026-03-25T02:00:00Z",
            "ends_at": "2026-03-25T04:00:00Z",
        },
        {
            "id": 103,
            "type": "unplanned",
            "state": "resolved",
            "subject": "Old incident",
        },
    ],
}


# -- detect() ----------------------------------------------------------------

@pytest.mark.asyncio
async def test_detect_valid():
    session = MockSession({API_ROOT: MockResponse(ROOT_JSON)})
    assert await SorryProvider.detect(session, URL, 10) is True


@pytest.mark.asyncio
async def test_detect_missing_state():
    data = {"page": {"links": {"components": "x", "notices": "y"}}}
    session = MockSession({API_ROOT: MockResponse(data)})
    assert await SorryProvider.detect(session, URL, 10) is False


@pytest.mark.asyncio
async def test_detect_missing_links():
    data = {"page": {"state": "operational"}}
    session = MockSession({API_ROOT: MockResponse(data)})
    assert await SorryProvider.detect(session, URL, 10) is False


# -- _parse() ----------------------------------------------------------------

def test_parse_full_response():
    data = SorryProvider._parse(ROOT_JSON, COMPONENTS_JSON, NOTICES_JSON, URL)

    assert data.page.name == "Example"
    assert data.status.indicator == "minor"
    assert data.status.description == "Some services are experiencing issues"

    # Only unplanned + active incidents are included (not resolved #103).
    assert len(data.incidents) == 1
    assert data.incidents[0].name == "High latency"
    assert data.incidents[0].body == "Looking into it."

    # Only planned + active maintenances.
    assert len(data.scheduled_maintenances) == 1
    assert data.scheduled_maintenances[0].name == "DB migration"

    assert len(data.components) == 2
    # Component 1 is a group header (referenced as parent_id by component 2).
    api_comp = next(c for c in data.components if c.id == "1")
    assert api_comp.group is True
    webapp_comp = next(c for c in data.components if c.id == "2")
    assert webapp_comp.group_id == "1"


def test_parse_operational_state():
    root = {"page": {"state": "operational", "name": "OK Service"}}
    data = SorryProvider._parse(root, {"components": []}, {"notices": []}, URL)
    assert data.status.indicator == "none"


def test_parse_empty_notices():
    data = SorryProvider._parse(ROOT_JSON, COMPONENTS_JSON, {"notices": []}, URL)
    assert data.incidents == []
    assert data.scheduled_maintenances == []


# -- fetch() ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fetch_returns_data():
    session = MockSession({
        API_ROOT: MockResponse(ROOT_JSON),
        COMPONENTS_URL: MockResponse(COMPONENTS_JSON),
        NOTICES_URL: MockResponse(NOTICES_JSON),
    })
    data = await SorryProvider.fetch(session, URL, 10)

    assert data.page.name == "Example"
    assert len(data.incidents) == 1
    assert len(data.components) == 2
