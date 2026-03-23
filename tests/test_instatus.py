"""Tests for the Instatus provider."""
from __future__ import annotations

import pytest

from custom_components.statuspage_monitor.providers.instatus import InstatusProvider

from .conftest import MockResponse, MockSession

URL = "https://status.example.com"
SUMMARY_URL = f"{URL}/summary.json"
COMPONENTS_URL = f"{URL}/v2/components.json"


SUMMARY_JSON = {
    "page": {
        "name": "Example App",
        "status": "HASISSUES",
    },
    "activeIncidents": [
        {
            "id": "inc1",
            "name": "API degradation",
            "status": "INVESTIGATING",
            "impact": "MAJOROUTAGE",
            "url": "https://status.example.com/inc1",
            "started": "2026-03-20T10:00:00Z",
            "updatedAt": "2026-03-20T10:30:00Z",
        },
    ],
    "activeMaintenances": [
        {
            "id": "mnt1",
            "name": "DB upgrade",
            "status": "INPROGRESS",
            "url": "https://status.example.com/mnt1",
            "start": "2026-03-20T02:00:00Z",
            "duration": "60",
        },
    ],
}

COMPONENTS_JSON = {
    "components": [
        {
            "id": "comp1",
            "name": "API",
            "status": "MAJOROUTAGE",
            "description": "Core API",
        },
        {
            "id": "comp2",
            "name": "Web App",
            "status": "OPERATIONAL",
            "group": {"id": "grp1"},
        },
        {
            "id": "grp1",
            "name": "Frontend",
            "status": "OPERATIONAL",
        },
    ],
}


# -- detect() ----------------------------------------------------------------

@pytest.mark.asyncio
async def test_detect_valid():
    """Instatus is detected when page.status is valid and no root 'components' key."""
    session = MockSession({SUMMARY_URL: MockResponse(SUMMARY_JSON)})
    assert await InstatusProvider.detect(session, URL, 10) is True


@pytest.mark.asyncio
async def test_detect_rejected_when_components_at_root():
    """Should reject if root-level 'components' key exists (Atlassian pattern)."""
    data = {**SUMMARY_JSON, "components": []}
    session = MockSession({SUMMARY_URL: MockResponse(data)})
    assert await InstatusProvider.detect(session, URL, 10) is False


@pytest.mark.asyncio
async def test_detect_rejected_unknown_status():
    data = {"page": {"status": "BANANA"}}
    session = MockSession({SUMMARY_URL: MockResponse(data)})
    assert await InstatusProvider.detect(session, URL, 10) is False


# -- _parse() ----------------------------------------------------------------

def test_parse_full_response():
    data = InstatusProvider._parse(SUMMARY_JSON, COMPONENTS_JSON, URL)

    assert data.page.name == "Example App"
    assert data.status.indicator == "major"

    assert len(data.incidents) == 1
    assert data.incidents[0].impact == "major"

    assert len(data.scheduled_maintenances) == 1
    assert data.scheduled_maintenances[0].scheduled_until is not None

    assert len(data.components) == 3
    # grp1 is a group header (referenced by comp2)
    grp = next(c for c in data.components if c.id == "grp1")
    assert grp.group is True
    child = next(c for c in data.components if c.id == "comp2")
    assert child.group_id == "grp1"


def test_parse_empty_incidents():
    summary = {"page": {"status": "UP"}}
    components = {"components": []}
    data = InstatusProvider._parse(summary, components, URL)

    assert data.status.indicator == "none"
    assert data.incidents == []
    assert data.components == []


def test_parse_resolved_incidents_filtered():
    summary = {
        "page": {"status": "UP"},
        "activeIncidents": [
            {"id": "inc1", "name": "Done", "status": "RESOLVED", "impact": "MINOROUTAGE"},
        ],
    }
    data = InstatusProvider._parse(summary, {"components": []}, URL)
    assert data.incidents == []


def test_parse_maintenance_without_duration():
    summary = {
        "page": {"status": "UNDERMAINTENANCE"},
        "activeMaintenances": [
            {"id": "m1", "name": "Quick fix", "status": "INPROGRESS", "start": "2026-03-20T02:00:00Z"},
        ],
    }
    data = InstatusProvider._parse(summary, {"components": []}, URL)
    assert data.scheduled_maintenances[0].scheduled_until is None


# -- fetch() ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fetch_returns_data():
    session = MockSession({
        SUMMARY_URL: MockResponse(SUMMARY_JSON),
        COMPONENTS_URL: MockResponse(COMPONENTS_JSON),
    })
    data = await InstatusProvider.fetch(session, URL, 10)

    assert data.page.name == "Example App"
    assert len(data.incidents) == 1
    assert len(data.components) == 3
