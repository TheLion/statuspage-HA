"""Constants for the Atlassian Statuspage integration."""

DOMAIN = "atlassian_statuspage"
PLATFORMS = ["sensor"]

# Configuration keys
CONF_URL = "url"
CONF_SCAN_INTERVAL = "scan_interval"

# Defaults and limits
# Atlassian Statuspage public JSON API has no published hard rate limits,
# but polling faster than 30 seconds is considered impolite and may result
# in temporary IP-level blocking. 60 seconds is the recommended default.
DEFAULT_SCAN_INTERVAL = 60  # seconds
MIN_SCAN_INTERVAL = 30  # seconds
MAX_SCAN_INTERVAL = 3600  # seconds

API_TIMEOUT = 15  # seconds

# API path
API_SUMMARY_PATH = "/api/v2/summary.json"

# Overall status indicator values (from status.indicator field)
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

# Component status values (from components[].status field)
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
