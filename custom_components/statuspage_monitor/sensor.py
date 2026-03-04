"""Sensor platform for StatusPage Monitor.

Creates the following sensors per configured status page:

  • Provider info            – name of the provider (e.g. "Atlassian")
  • Overall status          – enum: none / minor / major / critical
  • Active incidents        – integer count with incident details as attributes
  • Active incident body    – latest update text of the first active incident
                              (only for providers that support it)
  • Scheduled maintenances  – integer count with maintenance details
  • Per-component status    – enum: operational / degraded_performance /
                              partial_outage / major_outage / under_maintenance

Every sensor exposes ``icon`` and ``icon_color`` via extra_state_attributes so
that Mushroom template cards can read them with:
  icon:       "{{ state_attr(config.entity, 'icon') }}"
  icon_color: "{{ state_attr(config.entity, 'icon_color') }}"
"""
from __future__ import annotations

import base64
import logging
from pathlib import Path
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from .const import (
    COMPONENT_COLORS,
    COMPONENT_ICONS,
    COMPONENT_OPERATIONAL,
    COMPONENT_STATUS_OPTIONS,
    CONF_PAGE_NAME,
    CONF_PROVIDER,
    CONF_URL,
    DOMAIN,
    INDICATOR_COLORS,
    INDICATOR_ICONS,
    INDICATOR_NONE,
    INDICATOR_OPTIONS,
    PROVIDER_STATUSPAGE_IO,
)
from .coordinator import StatusPageMonitorCoordinator
from .providers import Component, StatusPageData, get_provider

_LOGGER = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Provider logos – loaded as base64 data URLs at import time so they render
# on ALL HA dashboard card types without needing HTTP requests or static paths.
# ---------------------------------------------------------------------------

def _load_provider_logos() -> dict[str, str]:
    """Return {provider_id: data_url} for every SVG in the logos directory."""
    logos_dir = Path(__file__).parent / "providers" / "logos"
    result: dict[str, str] = {}
    try:
        for svg_file in logos_dir.glob("*.svg"):
            b64 = base64.b64encode(svg_file.read_bytes()).decode()
            result[svg_file.stem] = f"data:image/svg+xml;base64,{b64}"
    except OSError:
        _LOGGER.warning("Could not load provider logos from %s", logos_dir)
    return result


_PROVIDER_LOGOS: dict[str, str] = _load_provider_logos()

# Map incident impact values to icon colours.
_IMPACT_COLORS: dict[str, str] = {
    "critical": "red",
    "major": "orange",
    "minor": "yellow",
    "none": "yellow",
}
_IMPACT_SEVERITY: dict[str, int] = {
    "critical": 3,
    "major": 2,
    "minor": 1,
    "none": 0,
}

# MDI icon fallbacks per provider (shown when entity_picture is unavailable).
_PROVIDER_ICONS: dict[str, str] = {
    "statuspage_io": "mdi:atlassian",
    "status_io": "mdi:heart-pulse",
    "uptimerobot": "mdi:robot",
    "instatus": "mdi:lightning-bolt",
    "cachet": "mdi:shield-check",
}


def _page_slug(coordinator: StatusPageMonitorCoordinator, entry: ConfigEntry) -> str:
    """Return a URL-safe slug derived from the status page name.

    Resolution order:
    1. Live page name from coordinator data (most accurate).
    2. Page name stored in config entry data (set during config flow — avoids
       race conditions where coordinator.data is not yet populated on first
       entity creation).
    3. URL fallback (last resort).
    """
    data: StatusPageData | None = coordinator.data
    name = (
        (data.page.name if data else None)
        or entry.data.get(CONF_PAGE_NAME)
        or entry.data[CONF_URL]
    )
    return slugify(name)


# ---------------------------------------------------------------------------
# Entity descriptions for the static (non-component) sensors
# ---------------------------------------------------------------------------

PROVIDER_INFO_DESCRIPTION = SensorEntityDescription(
    key="provider_info",
    translation_key="provider_info",
    has_entity_name=True,
    icon="mdi:information",
)

OVERALL_STATUS_DESCRIPTION = SensorEntityDescription(
    key="overall_status",
    translation_key="overall_status",
    has_entity_name=True,
    device_class=SensorDeviceClass.ENUM,
    options=INDICATOR_OPTIONS,
)

INCIDENTS_DESCRIPTION = SensorEntityDescription(
    key="active_incidents",
    translation_key="active_incidents",
    has_entity_name=True,
    native_unit_of_measurement="incidents",
    icon="mdi:alert-octagon",
)

MAINTENANCE_DESCRIPTION = SensorEntityDescription(
    key="scheduled_maintenances",
    translation_key="scheduled_maintenances",
    has_entity_name=True,
    native_unit_of_measurement="maintenances",
    icon="mdi:calendar-clock",
)

INCIDENT_BODY_DESCRIPTION = SensorEntityDescription(
    key="active_incident_description",
    translation_key="active_incident_description",
    has_entity_name=True,
    icon="mdi:text-box-outline",
)


# ---------------------------------------------------------------------------
# Platform setup
# ---------------------------------------------------------------------------


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up StatusPage Monitor sensors from a config entry.

    Static sensors (provider info, overall status, incidents, maintenances) are
    created immediately.  Component sensors are added on the first coordinator
    update and whenever new components appear in subsequent updates.

    The active_incident_description sensor is omitted for providers that do not
    expose incident body text (``SUPPORTS_INCIDENT_BODY = False``).
    """
    coordinator: StatusPageMonitorCoordinator = hass.data[DOMAIN][entry.entry_id]

    provider_id = entry.data.get(CONF_PROVIDER, PROVIDER_STATUSPAGE_IO)
    provider_class = get_provider(provider_id)
    supports_incident_body = getattr(provider_class, "SUPPORTS_INCIDENT_BODY", True)

    known_component_ids: set[str] = set()
    static_added = False

    @callback
    def _async_add_entities() -> None:
        nonlocal static_added
        entities: list[SensorEntity] = []

        if not static_added and coordinator.data:
            static: list[SensorEntity] = [
                ProviderInfoSensor(coordinator, entry),
                OverallStatusSensor(coordinator, entry),
                ActiveIncidentsSensor(coordinator, entry),
                ScheduledMaintenanceSensor(coordinator, entry),
            ]
            if supports_incident_body:
                static.insert(3, ActiveIncidentBodySensor(coordinator, entry))
            entities.extend(static)
            static_added = True

        for component in (coordinator.data.components if coordinator.data else []):
            if component.id not in known_component_ids:
                known_component_ids.add(component.id)
                entities.append(ComponentSensor(coordinator, entry, component))

        if entities:
            async_add_entities(entities)

    # Add initial entities if data is already available
    _async_add_entities()

    # Subscribe so that new components discovered in later updates are added
    entry.async_on_unload(coordinator.async_add_listener(_async_add_entities))


# ---------------------------------------------------------------------------
# Base entity
# ---------------------------------------------------------------------------


class _StatusPageEntity(
    CoordinatorEntity[StatusPageMonitorCoordinator], SensorEntity
):
    """Base class shared by all StatusPage Monitor sensor entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: StatusPageMonitorCoordinator,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry

    @property
    def device_info(self) -> DeviceInfo:
        """Group all sensors of a status page under one logical device."""
        data: StatusPageData | None = self.coordinator.data
        page_name = (data.page.name if data else None) or self._entry.data[CONF_URL]
        provider_name = (
            self._entry.data.get("provider", "statuspage_io")
            .replace("_", " ")
            .title()
        )
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name=page_name,
            manufacturer=provider_name,
            model="StatusPage Monitor",
            configuration_url=self._entry.data[CONF_URL],
        )


# ---------------------------------------------------------------------------
# Provider info sensor
# ---------------------------------------------------------------------------


class ProviderInfoSensor(_StatusPageEntity):
    """Sensor reporting the provider platform for this status page.

    State is the short provider name (e.g. "Atlassian", "Instatus", "Cachet").
    The entity_picture is set to the page's favicon so the provider logo is
    shown automatically in the frontend.
    """

    entity_description = PROVIDER_INFO_DESCRIPTION

    def __init__(
        self,
        coordinator: StatusPageMonitorCoordinator,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_provider_info"
        self.suggested_object_id = (
            f"statuspage_{_page_slug(coordinator, entry)}_provider_info"
        )

    @property
    def native_value(self) -> str:
        """Return the short provider name."""
        provider_id = self._entry.data.get(CONF_PROVIDER, PROVIDER_STATUSPAGE_IO)
        provider_class = get_provider(provider_id)
        return getattr(provider_class, "SHORT_NAME", provider_class.NAME)

    @property
    def entity_picture(self) -> str | None:
        """Return an embedded SVG data URL for the provider logo.

        Data URLs work in every HA card type (tile, entity, entities card) and
        the entity detail popup without needing HTTP requests or static paths.
        """
        provider_id = self._entry.data.get(CONF_PROVIDER, PROVIDER_STATUSPAGE_IO)
        return _PROVIDER_LOGOS.get(provider_id)

    @property
    def icon(self) -> str:
        """Fallback MDI icon used when entity_picture is not available."""
        provider_id = self._entry.data.get(CONF_PROVIDER, PROVIDER_STATUSPAGE_IO)
        return _PROVIDER_ICONS.get(provider_id, "mdi:information")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        provider_id = self._entry.data.get(CONF_PROVIDER, PROVIDER_STATUSPAGE_IO)
        provider_class = get_provider(provider_id)
        data: StatusPageData | None = self.coordinator.data
        attrs: dict[str, Any] = {
            "provider_id": provider_id,
            "provider_name": provider_class.NAME,
            "page_url": self._entry.data[CONF_URL],
            "icon": _PROVIDER_ICONS.get(provider_id, "mdi:information"),
        }
        if data and data.page.updated_at:
            attrs["page_updated_at"] = data.page.updated_at
        return attrs


# ---------------------------------------------------------------------------
# Overall status sensor
# ---------------------------------------------------------------------------


class OverallStatusSensor(_StatusPageEntity):
    """Sensor reporting the overall status indicator of the status page.

    State is one of: none, minor, major, critical.
    """

    entity_description = OVERALL_STATUS_DESCRIPTION

    def __init__(
        self,
        coordinator: StatusPageMonitorCoordinator,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_overall_status"
        self.suggested_object_id = (
            f"statuspage_{_page_slug(coordinator, entry)}_overall_status"
        )

    @property
    def native_value(self) -> str:
        """Return the indicator level."""
        data: StatusPageData | None = self.coordinator.data
        if not data:
            return INDICATOR_NONE
        indicator = data.status.indicator
        return indicator if indicator in INDICATOR_OPTIONS else INDICATOR_NONE

    @property
    def icon(self) -> str:
        return INDICATOR_ICONS.get(self.native_value, "mdi:help-circle")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data: StatusPageData | None = self.coordinator.data
        if not data:
            return {}
        return {
            "description": data.status.description,
            "page_name": data.page.name,
            "page_url": self._entry.data[CONF_URL],
            "page_updated_at": data.page.updated_at,
            "icon": self.icon,
            "icon_color": INDICATOR_COLORS.get(self.native_value, "grey"),
        }


# ---------------------------------------------------------------------------
# Active incidents sensor
# ---------------------------------------------------------------------------


class ActiveIncidentsSensor(_StatusPageEntity):
    """Sensor reporting the number of currently active (unresolved) incidents."""

    entity_description = INCIDENTS_DESCRIPTION

    def __init__(
        self,
        coordinator: StatusPageMonitorCoordinator,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_active_incidents"
        self.suggested_object_id = (
            f"statuspage_{_page_slug(coordinator, entry)}_active_incidents"
        )

    @property
    def native_value(self) -> int:
        return len(self._active_incidents)

    @property
    def icon(self) -> str:
        return "mdi:alert-octagon" if self.native_value > 0 else "mdi:check-circle"

    @property
    def _active_incidents(self):
        data: StatusPageData | None = self.coordinator.data
        return data.incidents if data else []

    @property
    def _icon_color(self) -> str:
        incidents = self._active_incidents
        if not incidents:
            return "green"
        worst = max(incidents, key=lambda i: _IMPACT_SEVERITY.get(i.impact, 0))
        return _IMPACT_COLORS.get(worst.impact, "yellow")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "icon": self.icon,
            "icon_color": self._icon_color,
            "incidents": [
                {
                    "id": inc.id,
                    "name": inc.name,
                    "status": inc.status,
                    "impact": inc.impact,
                    "shortlink": inc.shortlink,
                    "started_at": inc.started_at,
                    "updated_at": inc.updated_at,
                }
                for inc in self._active_incidents
            ],
        }


# ---------------------------------------------------------------------------
# Active incident body sensor
# ---------------------------------------------------------------------------


class ActiveIncidentBodySensor(_StatusPageEntity):
    """Sensor reporting the latest update text of the first active incident.

    The state is the body text of the most recent incident update, ready to
    use directly in a Markdown card or as a notification message.  When there
    are no active incidents the state is None (shown as 'unknown' in HA).

    This sensor is only created for providers that expose incident body text
    (``SUPPORTS_INCIDENT_BODY = True``, which is the default).
    """

    entity_description = INCIDENT_BODY_DESCRIPTION

    def __init__(
        self,
        coordinator: StatusPageMonitorCoordinator,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_active_incident_description"
        self.suggested_object_id = (
            f"statuspage_{_page_slug(coordinator, entry)}_active_incident_description"
        )

    @property
    def _first_incident(self):
        data: StatusPageData | None = self.coordinator.data
        incidents = data.incidents if data else []
        return incidents[0] if incidents else None

    @property
    def native_value(self) -> str | None:
        inc = self._first_incident
        return inc.body if inc else None

    @property
    def icon(self) -> str:
        return "mdi:text-box-outline" if self._first_incident else "mdi:text-box-check-outline"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        inc = self._first_incident
        color = _IMPACT_COLORS.get(inc.impact, "yellow") if inc else "green"
        if not inc:
            return {
                "icon": self.icon,
                "icon_color": color,
            }
        return {
            "incident_id": inc.id,
            "incident_name": inc.name,
            "incident_status": inc.status,
            "incident_impact": inc.impact,
            "icon": self.icon,
            "icon_color": color,
        }


# ---------------------------------------------------------------------------
# Scheduled maintenance sensor
# ---------------------------------------------------------------------------


class ScheduledMaintenanceSensor(_StatusPageEntity):
    """Sensor reporting the number of upcoming scheduled maintenances."""

    entity_description = MAINTENANCE_DESCRIPTION

    def __init__(
        self,
        coordinator: StatusPageMonitorCoordinator,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_scheduled_maintenances"
        self.suggested_object_id = (
            f"statuspage_{_page_slug(coordinator, entry)}_scheduled_maintenances"
        )

    @property
    def native_value(self) -> int:
        data: StatusPageData | None = self.coordinator.data
        return len(data.scheduled_maintenances) if data else 0

    @property
    def icon(self) -> str:
        return "mdi:calendar-alert" if self.native_value > 0 else "mdi:calendar-check"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data: StatusPageData | None = self.coordinator.data
        maintenances = data.scheduled_maintenances if data else []
        return {
            "icon": self.icon,
            "icon_color": "blue" if self.native_value > 0 else "green",
            "maintenances": [
                {
                    "id": m.id,
                    "name": m.name,
                    "status": m.status,
                    "impact": m.impact,
                    "shortlink": m.shortlink,
                    "scheduled_for": m.scheduled_for,
                    "scheduled_until": m.scheduled_until,
                }
                for m in maintenances
            ],
        }


# ---------------------------------------------------------------------------
# Per-component sensor
# ---------------------------------------------------------------------------


class ComponentSensor(_StatusPageEntity):
    """Sensor for a single service component on the status page.

    The sensor is identified by the stable component ``id`` returned by the
    provider, so it survives renames of the component on the status page.
    """

    def __init__(
        self,
        coordinator: StatusPageMonitorCoordinator,
        entry: ConfigEntry,
        component: Component,
    ) -> None:
        super().__init__(coordinator, entry)
        self._component_id: str = component.id
        self._attr_unique_id = f"{entry.entry_id}_{self._component_id}"
        page_slug = _page_slug(coordinator, entry)
        component_slug = slugify(component.name)
        if component_slug.startswith(page_slug + "_"):
            component_slug = component_slug[len(page_slug) + 1:]
        self.suggested_object_id = f"statuspage_{page_slug}_{component_slug}"
        self._attr_has_entity_name = True
        self._attr_translation_key = "component_status"
        self._attr_device_class = SensorDeviceClass.ENUM
        self._attr_options = COMPONENT_STATUS_OPTIONS

    @property
    def name(self) -> str:
        comp = self._component_data
        if not comp:
            return self._component_id
        data = self.coordinator.data
        page_name = data.page.name if data else ""
        name = comp.name
        if page_name and name.lower().startswith(page_name.lower() + " "):
            name = name[len(page_name) + 1:]
        return name

    @property
    def native_value(self) -> str:
        comp = self._component_data
        if not comp:
            return COMPONENT_OPERATIONAL
        return comp.status if comp.status in COMPONENT_STATUS_OPTIONS else COMPONENT_OPERATIONAL

    @property
    def icon(self) -> str:
        return COMPONENT_ICONS.get(self.native_value, "mdi:help-circle")

    @property
    def _component_data(self) -> Component | None:
        data: StatusPageData | None = self.coordinator.data
        if not data:
            return None
        for comp in data.components:
            if comp.id == self._component_id:
                return comp
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        comp = self._component_data
        color = COMPONENT_COLORS.get(self.native_value, "grey")
        if not comp:
            return {
                "component_id": self._component_id,
                "icon": self.icon,
                "icon_color": color,
            }
        return {
            "component_id": self._component_id,
            "description": comp.description,
            "group": comp.group,
            "group_id": comp.group_id,
            "updated_at": comp.updated_at,
            "showcase": comp.showcase,
            "icon": self.icon,
            "icon_color": color,
        }

    @property
    def available(self) -> bool:
        """Mark unavailable if component data has disappeared from the API."""
        return super().available and self._component_data is not None
