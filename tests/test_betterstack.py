"""Tests for the Better Stack provider."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from custom_components.statuspage_monitor.providers.betterstack import (
    BetterStackProvider,
)

from .conftest import MockResponse, MockSession

URL = "https://status.example.com"
INDEX_URL = f"{URL}/index.json"


def _payload(
    aggregate_state: str = "operational",
    resources: list[dict] | None = None,
    sections: list[dict] | None = None,
    reports: list[dict] | None = None,
    announcement: str | None = None,
) -> dict:
    """Build a minimal JSON:API payload that mirrors /index.json."""
    return {
        "data": {
            "id": "1",
            "type": "status_page",
            "attributes": {
                "company_name": "Example App",
                "aggregate_state": aggregate_state,
                "announcement": announcement,
                "updated_at": "2026-05-11T12:00:00Z",
            },
        },
        "included": (sections or []) + (resources or []) + (reports or []),
    }


SECTION = {
    "id": "10",
    "type": "status_page_section",
    "attributes": {"name": "Core", "position": 0},
}

RESOURCE = {
    "id": "100",
    "type": "status_page_resource",
    "attributes": {
        "status_page_section_id": 10,
        "public_name": "API",
        "status": "operational",
        "explanation": "",
    },
}


# -- detect() ----------------------------------------------------------------

@pytest.mark.asyncio
async def test_detect_valid():
    session = MockSession({INDEX_URL: MockResponse(_payload())})
    assert await BetterStackProvider.detect(session, URL, 10) is True


@pytest.mark.asyncio
async def test_detect_rejects_wrong_type():
    payload = _payload()
    payload["data"]["type"] = "something_else"
    session = MockSession({INDEX_URL: MockResponse(payload)})
    assert await BetterStackProvider.detect(session, URL, 10) is False


@pytest.mark.asyncio
async def test_detect_rejects_404():
    session = MockSession({INDEX_URL: MockResponse(status=404)})
    assert await BetterStackProvider.detect(session, URL, 10) is False


# -- _parse() ----------------------------------------------------------------

def test_parse_operational():
    data = BetterStackProvider._parse(
        _payload(resources=[RESOURCE], sections=[SECTION]),
        URL,
    )
    assert data.page.name == "Example App"
    assert data.status.indicator == "none"
    # Section is emitted as a group header + the resource itself
    assert len(data.components) == 2
    section = next(c for c in data.components if c.group)
    assert section.id == "10"
    assert section.name == "Core"
    resource = next(c for c in data.components if not c.group)
    assert resource.id == "100"
    assert resource.group_id == "10"
    assert resource.status == "operational"


def test_parse_downtime_maps_to_critical_and_major_outage():
    resource = {
        **RESOURCE,
        "attributes": {**RESOURCE["attributes"], "status": "downtime"},
    }
    data = BetterStackProvider._parse(
        _payload(aggregate_state="downtime", resources=[resource]),
        URL,
    )
    assert data.status.indicator == "critical"
    res = next(c for c in data.components if not c.group)
    assert res.status == "major_outage"


def test_parse_degraded_maps_to_minor():
    data = BetterStackProvider._parse(
        _payload(aggregate_state="degraded", resources=[RESOURCE]),
        URL,
    )
    assert data.status.indicator == "minor"


def test_parse_maintenance_indicator_is_none():
    data = BetterStackProvider._parse(
        _payload(aggregate_state="maintenance", resources=[RESOURCE]),
        URL,
    )
    # Page-level maintenance falls through to "none" (Instatus convention).
    assert data.status.indicator == "none"


def test_parse_empty_sections_are_dropped():
    # Section exists but no resource references it → skip header.
    payload = _payload(sections=[SECTION])
    data = BetterStackProvider._parse(payload, URL)
    assert data.components == []


def test_parse_skips_resolved_incident():
    report = {
        "id": "500",
        "type": "status_report",
        "attributes": {
            "title": "Dashboard hiccup",
            "report_type": "manual",
            "starts_at": "2026-04-20T19:00:00Z",
            "ends_at": None,
            "affected_resources": [{"status_page_resource_id": "100", "status": "resolved"}],
            "aggregate_state": "resolved",
        },
    }
    data = BetterStackProvider._parse(_payload(reports=[report]), URL)
    assert data.incidents == []


def test_parse_active_incident_impact_from_affected():
    report = {
        "id": "501",
        "type": "status_report",
        "attributes": {
            "title": "API outage",
            "report_type": "manual",
            "starts_at": "2026-05-11T11:00:00Z",
            "ends_at": None,
            "affected_resources": [
                {"status_page_resource_id": "100", "status": "downtime"},
            ],
            "aggregate_state": "investigating",
        },
    }
    data = BetterStackProvider._parse(_payload(reports=[report]), URL)
    assert len(data.incidents) == 1
    inc = data.incidents[0]
    assert inc.name == "API outage"
    assert inc.status == "investigating"
    assert inc.impact == "major"


def test_parse_maintenance_completed_is_skipped():
    past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    report = {
        "id": "600",
        "type": "status_report",
        "attributes": {
            "title": "Old maint",
            "report_type": "maintenance",
            "starts_at": "2026-04-14T07:00:00Z",
            "ends_at": past,
            "affected_resources": [],
            "aggregate_state": "maintenance",
        },
    }
    data = BetterStackProvider._parse(_payload(reports=[report]), URL)
    assert data.scheduled_maintenances == []


def test_parse_maintenance_scheduled_in_future():
    future = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    report = {
        "id": "601",
        "type": "status_report",
        "attributes": {
            "title": "Planned upgrade",
            "report_type": "maintenance",
            "starts_at": future,
            "ends_at": None,
            "affected_resources": [],
            "aggregate_state": "maintenance",
        },
    }
    data = BetterStackProvider._parse(_payload(reports=[report]), URL)
    assert len(data.scheduled_maintenances) == 1
    assert data.scheduled_maintenances[0].status == "scheduled"


def test_parse_maintenance_in_progress():
    now = datetime.now(timezone.utc)
    started = (now - timedelta(minutes=10)).isoformat()
    ends = (now + timedelta(hours=1)).isoformat()
    report = {
        "id": "602",
        "type": "status_report",
        "attributes": {
            "title": "Active maint",
            "report_type": "maintenance",
            "starts_at": started,
            "ends_at": ends,
            "affected_resources": [],
            "aggregate_state": "maintenance",
        },
    }
    data = BetterStackProvider._parse(_payload(reports=[report]), URL)
    assert len(data.scheduled_maintenances) == 1
    assert data.scheduled_maintenances[0].status == "in_progress"


def test_parse_uses_announcement_as_description():
    data = BetterStackProvider._parse(
        _payload(announcement="We've moved our API servers!"),
        URL,
    )
    assert data.status.description == "We've moved our API servers!"


# -- fetch() ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fetch_returns_data():
    payload = _payload(resources=[RESOURCE], sections=[SECTION])
    session = MockSession({INDEX_URL: MockResponse(payload)})
    data = await BetterStackProvider.fetch(session, URL, 10)
    assert data.page.name == "Example App"
    assert len(data.components) == 2
