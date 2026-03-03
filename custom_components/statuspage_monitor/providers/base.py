"""Shared data model and provider Protocol for StatusPage Monitor.

All provider implementations must:
  1. Set class-level ID and NAME strings.
  2. Implement detect() – return True if the URL looks like this platform.
  3. Implement fetch() – return a fully populated StatusPageData.

The data classes below use the same normalised state values that the sensor
platform exposes, so providers are responsible for mapping platform-specific
values to these canonical strings.

Overall status indicator (OverallStatus.indicator):
  "none"     – all systems operational
  "minor"    – minor degradation
  "major"    – major degradation / partial outage
  "critical" – widespread / critical outage

Component status (Component.status):
  "operational"          – fully operational
  "degraded_performance" – degraded
  "partial_outage"       – partial outage
  "major_outage"         – major outage
  "under_maintenance"    – planned maintenance
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, ClassVar, Protocol, runtime_checkable

if TYPE_CHECKING:
    import aiohttp


@dataclass
class PageInfo:
    """Metadata about the status page itself."""

    name: str
    url: str
    updated_at: str | None = None


@dataclass
class OverallStatus:
    """Top-level health indicator for the entire service."""

    indicator: str  # none | minor | major | critical
    description: str | None = None


@dataclass
class Incident:
    """A single active or recent incident."""

    id: str
    name: str
    status: str
    impact: str
    shortlink: str | None = None
    started_at: str | None = None
    updated_at: str | None = None
    body: str | None = None


@dataclass
class Maintenance:
    """A scheduled maintenance window."""

    id: str
    name: str
    status: str
    impact: str
    shortlink: str | None = None
    scheduled_for: str | None = None
    scheduled_until: str | None = None


@dataclass
class Component:
    """Health status of a single service component."""

    id: str
    name: str
    status: str
    description: str | None = None
    group: bool = False
    group_id: str | None = None
    updated_at: str | None = None
    showcase: bool | None = None


@dataclass
class StatusPageData:
    """Normalised status snapshot returned by every provider."""

    page: PageInfo
    status: OverallStatus
    incidents: list[Incident] = field(default_factory=list)
    scheduled_maintenances: list[Maintenance] = field(default_factory=list)
    components: list[Component] = field(default_factory=list)


@runtime_checkable
class StatusPageProvider(Protocol):
    """Protocol that every statuspage provider must satisfy."""

    ID: ClassVar[str]
    NAME: ClassVar[str]

    @classmethod
    async def detect(
        cls,
        session: aiohttp.ClientSession,
        url: str,
        timeout: int,
    ) -> bool:
        """Return True if *url* is served by this provider platform."""
        ...

    @classmethod
    async def fetch(
        cls,
        session: aiohttp.ClientSession,
        url: str,
        timeout: int,
    ) -> StatusPageData:
        """Fetch current status and return a normalised StatusPageData."""
        ...
