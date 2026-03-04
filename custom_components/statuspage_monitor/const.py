"""Constants for the Status Page Monitor integration."""

DOMAIN = "statuspage_monitor"
PLATFORMS = ["sensor"]

# Configuration keys
CONF_URL = "url"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_PROVIDER = "provider"

# Defaults and limits
DEFAULT_SCAN_INTERVAL = 60  # seconds
MIN_SCAN_INTERVAL = 30  # seconds
MAX_SCAN_INTERVAL = 3600  # seconds

API_TIMEOUT = 15  # seconds

# Provider identifiers (must match the ID class variable in each provider)
PROVIDER_STATUSPAGE_IO = "statuspage_io"
PROVIDER_STATUS_IO = "status_io"
PROVIDER_UPTIMEROBOT = "uptimerobot"

# Overall status indicator values (normalised – shared across all providers)
INDICATOR_NONE = "none"
INDICATOR_MINOR = "minor"
INDICATOR_MAJOR = "major"
INDICATOR_CRITICAL = "critical"

INDICATOR_OPTIONS = [
    INDICATOR_NONE,
    INDICATOR_MINOR,
    INDICATOR_MAJOR,
    INDICATOR_CRITICAL,
]

# Component status values (normalised – shared across all providers)
COMPONENT_OPERATIONAL = "operational"
COMPONENT_DEGRADED = "degraded_performance"
COMPONENT_PARTIAL_OUTAGE = "partial_outage"
COMPONENT_MAJOR_OUTAGE = "major_outage"
COMPONENT_MAINTENANCE = "under_maintenance"

COMPONENT_STATUS_OPTIONS = [
    COMPONENT_OPERATIONAL,
    COMPONENT_DEGRADED,
    COMPONENT_PARTIAL_OUTAGE,
    COMPONENT_MAJOR_OUTAGE,
    COMPONENT_MAINTENANCE,
]

# Icons per indicator state
INDICATOR_ICONS = {
    INDICATOR_NONE: "mdi:check-circle",
    INDICATOR_MINOR: "mdi:alert",
    INDICATOR_MAJOR: "mdi:alert-circle",
    INDICATOR_CRITICAL: "mdi:close-circle",
}

# Icons per component status
COMPONENT_ICONS = {
    COMPONENT_OPERATIONAL: "mdi:check-circle",
    COMPONENT_DEGRADED: "mdi:alert",
    COMPONENT_PARTIAL_OUTAGE: "mdi:alert-circle",
    COMPONENT_MAJOR_OUTAGE: "mdi:close-circle",
    COMPONENT_MAINTENANCE: "mdi:wrench-clock",
}

# Icon colors per indicator state (CSS / HA color names)
INDICATOR_COLORS = {
    INDICATOR_NONE: "green",
    INDICATOR_MINOR: "yellow",
    INDICATOR_MAJOR: "orange",
    INDICATOR_CRITICAL: "red",
}

# Icon colors per component status
COMPONENT_COLORS = {
    COMPONENT_OPERATIONAL: "green",
    COMPONENT_DEGRADED: "yellow",
    COMPONENT_PARTIAL_OUTAGE: "orange",
    COMPONENT_MAJOR_OUTAGE: "red",
    COMPONENT_MAINTENANCE: "blue",
}

# Stored in config entry during setup so entity IDs are stable before first data fetch
CONF_PAGE_NAME = "page_name"
