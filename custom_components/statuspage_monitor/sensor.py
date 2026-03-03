"""Sensor platform for StatusPage Monitor.

Creates the following sensors per configured status page:

  • Overall status          – enum: none / minor / major / critical
  • Active incidents        – integer count with incident details as attributes
  • Active incident body    – latest update text of the first active incident
  • Scheduled maintenances  – integer count with maintenance details
  • Per-component status    – enum: operational / degraded_performance /
                              partial_outage / major_outage / under_maintenance

The icon_color attribute is exposed via extra_state_attributes so that
Mushroom template cards can read it with:
  icon_color: "{{ state_attr(config.entity, 'icon_color') }}"
"""
from __future__ import annotations

import logging
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
    CONF_URL,
    DOMAIN,
    INDICATOR_COLORS,
    INDICATOR_ICONS,
    INDICATOR_NONE,
    INDICATOR_OPTIONS,
)
from .coordinator import StatusPageMonitorCoordinator
from .providers.base import Component, StatusPageData

_LOGGER = logging.getLogger(__name__)


def _page_slug(coordinator: StatusPageMonitorCoordinator, entry: ConfigEntry) -> str:
    """Return a URL-safe slug derived from the status page name (or URL fallback)."""
    data: StatusPageData | None = coordinator.data
    name = (data.page.name if data else None) or entry.data[CONF_URL]
    return slugify(name)


# ---------------------------------------------------------------------------
# Entity descriptions for the static (non-component) sensors
# ---------------------------------------------------------------------------

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

    Static sensors (overall status, incidents, maintenances) are created
    immediately.  Component sensors are added on the first coordinator
    update and whenever new components appear in subsequent updates.
    """
    coordinator: StatusPageMonitorCoordinator = hass.data[DOMAIN][entry.entry_id]

    known_component_ids: set[str] = set()
    static_added = False

    @callback
    def _async_add_entities() -> None:
        nonlocal static_added
        entities: list[SensorEntity] = []

        if not static_added and coordinator.data:
            entities.extend(
                [
                    OverallStatusSensor(coordinator, entry),
                    ActiveIncidentsSensor(coordinator, entry),
                    ActiveIncidentBodySensor(coordinator, entry),
                    ScheduledMaintenanceSensor(coordinator, entry),
                ]
            )
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
        self._attr_suggested_object_id = (
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
        self._attr_suggested_object_id = (
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
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
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
            ]
        }


# ---------------------------------------------------------------------------
# Active incident body sensor
# ---------------------------------------------------------------------------


class ActiveIncidentBodySensor(_StatusPageEntity):
    """Sensor reporting the latest update text of the first active incident.

    The state is the body text of the most recent incident update, ready to
    use directly in a Markdown card or as a notification message.  When there
    are no active incidents the state is None (shown as 'unknown' in HA).
    """

    entity_description = INCIDENT_BODY_DESCRIPTION

    def __init__(
        self,
        coordinator: StatusPageMonitorCoordinator,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_active_incident_description"
        self._attr_suggested_object_id = (
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
        if not inc:
            return {}
        return {
            "incident_id": inc.id,
            "incident_name": inc.name,
            "incident_status": inc.status,
            "incident_impact": inc.impact,
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
        self._attr_suggested_object_id = (
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
            ]
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
        self._attr_suggested_object_id = (
            f"statuspage_{_page_slug(coordinator, entry)}_{slugify(component.name)}"
        )
        self._attr_has_entity_name = True
        self._attr_translation_key = "component_status"
        self._attr_device_class = SensorDeviceClass.ENUM
        self._attr_options = COMPONENT_STATUS_OPTIONS

    @property
    def name(self) -> str:
        comp = self._component_data
        return comp.name if comp else self._component_id

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
            return {"component_id": self._component_id, "icon_color": color}
        return {
            "component_id": self._component_id,
            "description": comp.description,
            "group": comp.group,
            "group_id": comp.group_id,
            "updated_at": comp.updated_at,
            "showcase": comp.showcase,
            "icon_color": color,
        }

    @property
    def available(self) -> bool:
        """Mark unavailable if component data has disappeared from the API."""
        return super().available and self._component_data is not None
