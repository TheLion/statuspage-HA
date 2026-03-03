"""Sensor platform for Atlassian Statuspage integration.

Creates the following sensors per configured status page:

  • Overall status          – enum: none / minor / major / critical
  • Active incidents        – integer count with incident details as attributes
  • Scheduled maintenances  – integer count with maintenance details
  • Per-component status    – enum: operational / degraded_performance /
                              partial_outage / major_outage / under_maintenance

Sensor icons change dynamically to provide an immediate visual colour cue:
  ✅  mdi:check-circle      → operational / no issues
  ⚠️  mdi:alert             → degraded / minor issue
  🔶  mdi:alert-circle      → partial outage / major issue
  🔴  mdi:close-circle      → major outage / critical issue
  🔧  mdi:wrench-clock      → under maintenance

For richer colour feedback in Lovelace, enable ``state_color: true`` on an
Entity card – the icon colour will then reflect the entity state.
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

from .const import (
    COMPONENT_ICONS,
    COMPONENT_MAJOR_OUTAGE,
    COMPONENT_MAINTENANCE,
    COMPONENT_OPERATIONAL,
    COMPONENT_STATUS_OPTIONS,
    CONF_URL,
    DOMAIN,
    INDICATOR_CRITICAL,
    INDICATOR_ICONS,
    INDICATOR_MINOR,
    INDICATOR_NONE,
    INDICATOR_OPTIONS,
)
from .coordinator import StatuspageCoordinator

_LOGGER = logging.getLogger(__name__)

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


# ---------------------------------------------------------------------------
# Platform setup
# ---------------------------------------------------------------------------


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Statuspage sensors from a config entry.

    Static sensors (overall status, incidents, maintenances) are created
    immediately.  Component sensors are added on the first coordinator
    update and whenever new components appear in subsequent updates.
    """
    coordinator: StatuspageCoordinator = hass.data[DOMAIN][entry.entry_id]

    known_component_ids: set[str] = set()
    static_added = False

    @callback
    def _async_add_entities() -> None:
        nonlocal static_added
        entities: list[SensorEntity] = []

        if not static_added and coordinator.data:
            entities.extend(
                [
                    StatuspageOverallStatusSensor(coordinator, entry),
                    StatuspageIncidentsSensor(coordinator, entry),
                    StatuspageMaintenanceSensor(coordinator, entry),
                ]
            )
            static_added = True

        for component in (coordinator.data or {}).get("components", []):
            comp_id = component.get("id")
            if comp_id and comp_id not in known_component_ids:
                known_component_ids.add(comp_id)
                entities.append(
                    StatuspageComponentSensor(coordinator, entry, component)
                )

        if entities:
            async_add_entities(entities)

    # Add initial entities if data is already available
    _async_add_entities()

    # Subscribe so that new components discovered in later updates are added
    entry.async_on_unload(coordinator.async_add_listener(_async_add_entities))


# ---------------------------------------------------------------------------
# Base entity
# ---------------------------------------------------------------------------


class _StatuspageEntity(CoordinatorEntity[StatuspageCoordinator], SensorEntity):
    """Base class shared by all Statuspage sensor entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: StatuspageCoordinator,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry

    @property
    def device_info(self) -> DeviceInfo:
        """Group all sensors of a status page under one logical device."""
        data = self.coordinator.data or {}
        page = data.get("page", {})
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name=page.get("name") or self._entry.data[CONF_URL],
            manufacturer="Atlassian",
            model="Statuspage",
            configuration_url=self._entry.data[CONF_URL],
        )


# ---------------------------------------------------------------------------
# Overall status sensor
# ---------------------------------------------------------------------------


class StatuspageOverallStatusSensor(_StatuspageEntity):
    """Sensor reporting the overall status indicator of the status page.

    State is one of: none, minor, major, critical.
    Icon colour:
      none     → mdi:check-circle   (all operational)
      minor    → mdi:alert          (minor degradation)
      major    → mdi:alert-circle   (major degradation)
      critical → mdi:close-circle   (critical / widespread outage)
    """

    entity_description = OVERALL_STATUS_DESCRIPTION

    def __init__(
        self,
        coordinator: StatuspageCoordinator,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_overall_status"

    @property
    def native_value(self) -> str | None:
        """Return the indicator level."""
        data = self.coordinator.data or {}
        indicator = data.get("status", {}).get("indicator")
        if indicator not in INDICATOR_OPTIONS:
            return INDICATOR_NONE
        return indicator

    @property
    def icon(self) -> str:
        """Return an icon that reflects the current indicator."""
        return INDICATOR_ICONS.get(self.native_value or INDICATOR_NONE, "mdi:help-circle")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose additional details as attributes."""
        data = self.coordinator.data or {}
        status = data.get("status", {})
        page = data.get("page", {})
        return {
            "description": status.get("description"),
            "page_name": page.get("name"),
            "page_url": self._entry.data[CONF_URL],
            "page_updated_at": page.get("updated_at"),
        }


# ---------------------------------------------------------------------------
# Active incidents sensor
# ---------------------------------------------------------------------------


class StatuspageIncidentsSensor(_StatuspageEntity):
    """Sensor reporting the number of currently active (unresolved) incidents.

    Active = any incident whose status is NOT 'resolved'.
    Attributes include a summary list of active incidents.
    """

    entity_description = INCIDENTS_DESCRIPTION

    def __init__(
        self,
        coordinator: StatuspageCoordinator,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_active_incidents"

    @property
    def native_value(self) -> int:
        """Return number of unresolved incidents."""
        return len(self._active_incidents)

    @property
    def icon(self) -> str:
        """Red icon when there are incidents, neutral when clear."""
        return "mdi:alert-octagon" if self.native_value > 0 else "mdi:check-circle"

    @property
    def _active_incidents(self) -> list[dict]:
        data = self.coordinator.data or {}
        return [
            i
            for i in data.get("incidents", [])
            if i.get("status") != "resolved"
        ]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        incidents = self._active_incidents
        return {
            "incidents": [
                {
                    "id": inc.get("id"),
                    "name": inc.get("name"),
                    "status": inc.get("status"),
                    "impact": inc.get("impact"),
                    "shortlink": inc.get("shortlink"),
                    "started_at": inc.get("started_at"),
                    "updated_at": inc.get("updated_at"),
                }
                for inc in incidents
            ]
        }


# ---------------------------------------------------------------------------
# Scheduled maintenance sensor
# ---------------------------------------------------------------------------


class StatuspageMaintenanceSensor(_StatuspageEntity):
    """Sensor reporting the number of upcoming scheduled maintenances."""

    entity_description = MAINTENANCE_DESCRIPTION

    def __init__(
        self,
        coordinator: StatuspageCoordinator,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_scheduled_maintenances"

    @property
    def native_value(self) -> int:
        """Return number of scheduled maintenances."""
        return len((self.coordinator.data or {}).get("scheduled_maintenances", []))

    @property
    def icon(self) -> str:
        """Calendar-alert icon when maintenance is planned."""
        return (
            "mdi:calendar-alert"
            if self.native_value > 0
            else "mdi:calendar-check"
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        maintenances = (self.coordinator.data or {}).get("scheduled_maintenances", [])
        return {
            "maintenances": [
                {
                    "id": m.get("id"),
                    "name": m.get("name"),
                    "status": m.get("status"),
                    "impact": m.get("impact"),
                    "shortlink": m.get("shortlink"),
                    "scheduled_for": m.get("scheduled_for"),
                    "scheduled_until": m.get("scheduled_until"),
                }
                for m in maintenances
            ]
        }


# ---------------------------------------------------------------------------
# Per-component sensor
# ---------------------------------------------------------------------------


class StatuspageComponentSensor(_StatuspageEntity):
    """Sensor for a single component on the status page.

    State is one of:
      operational          → mdi:check-circle
      degraded_performance → mdi:alert
      partial_outage       → mdi:alert-circle
      major_outage         → mdi:close-circle
      under_maintenance    → mdi:wrench-clock

    The sensor is identified by the stable component ``id`` returned by the
    API, so it survives renames of the component on the status page.
    """

    def __init__(
        self,
        coordinator: StatuspageCoordinator,
        entry: ConfigEntry,
        component: dict,
    ) -> None:
        super().__init__(coordinator, entry)
        self._component_id: str = component["id"]
        # Use the initial name; will update dynamically via native_value / attrs
        self._attr_unique_id = f"{entry.entry_id}_{self._component_id}"
        self._attr_has_entity_name = True
        self._attr_translation_key = "component_status"
        self._attr_device_class = SensorDeviceClass.ENUM
        self._attr_options = COMPONENT_STATUS_OPTIONS

    @property
    def name(self) -> str:
        """Return the component name as the entity name."""
        component = self._component_data
        return component.get("name") or self._component_id

    @property
    def native_value(self) -> str | None:
        """Return the component status."""
        component = self._component_data
        status = component.get("status")
        if status not in COMPONENT_STATUS_OPTIONS:
            return COMPONENT_OPERATIONAL
        return status

    @property
    def icon(self) -> str:
        """Return an icon that reflects the component status."""
        return COMPONENT_ICONS.get(
            self.native_value or COMPONENT_OPERATIONAL, "mdi:help-circle"
        )

    @property
    def _component_data(self) -> dict:
        """Look up this component's current data from the coordinator."""
        for comp in (self.coordinator.data or {}).get("components", []):
            if comp.get("id") == self._component_id:
                return comp
        return {}

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        component = self._component_data
        return {
            "component_id": self._component_id,
            "description": component.get("description"),
            "group": component.get("group", False),
            "group_id": component.get("group_id"),
            "updated_at": component.get("updated_at"),
            "showcase": component.get("showcase"),
        }

    @property
    def available(self) -> bool:
        """Mark unavailable if component data has disappeared from the API."""
        return super().available and bool(self._component_data)
