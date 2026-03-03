# Status Page Monitor – Home Assistant Integration

Monitor any compatible status page from Home Assistant. The integration
automatically creates sensors for the overall status, active incidents,
scheduled maintenances, and every individual service component.

Examples of supported status pages:

| Service | URL |
|---------|-----|
| Claude (Anthropic) | https://status.claude.com |
| Atlassian | https://status.atlassian.com |
| GitHub | https://www.githubstatus.com |
| Cloudflare | https://www.cloudflarestatus.com |
| Datadog | https://status.datadoghq.com |
| Twilio | https://status.twilio.com |

The provider platform is detected automatically from the URL — just enter the
address and the integration handles the rest.

---

## Supported providers

| Provider | Status | Notes |
|----------|--------|-------|
| **Atlassian Statuspage** (statuspage.io) | ✅ Supported | Any service hosted on the Atlassian Statuspage platform, including self-hosted instances |
| Status.io | 🔜 Planned | Implementation guide available in `providers/status_io.py` |
| UptimeRobot Status Pages | 🔜 Planned | Implementation guide available in `providers/uptimerobot.py` |

> Hundreds of services use the Atlassian Statuspage platform, so most public
> status pages you will encounter are already supported today.

### Adding a new provider

The integration uses a pluggable provider system. To add support for a new
platform, create a single Python file in `custom_components/statuspage_monitor/providers/`
that implements `detect()` and `fetch()`, then add the class to the `PROVIDERS`
list in `providers/__init__.py`. No other files need to change.

---

## How it works

The integration polls the status page API on a configurable interval
(default 60 s). A single HTTP call returns everything needed:

- Page metadata (name, URL, last updated timestamp)
- Overall status indicator
- Status of every individual component
- Active (unresolved) incidents
- Scheduled maintenance windows

### Atlassian Statuspage API

For Statuspage.io-hosted pages, the integration calls `/api/v2/summary.json`.

| Method | Component status | Structured | Stable |
|--------|:---------------:|:----------:|:------:|
| **JSON API** (chosen) | ✅ | ✅ | ✅ |
| RSS / Atom feed | ❌ (incidents only) | ✅ | ✅ |
| Web scraping | ✅ | ❌ | ❌ |

RSS/Atom feeds only contain incident history, not real-time component status.
Web scraping breaks whenever the HTML changes. The JSON API is the only option
that delivers all required information in a stable, structured format.

### Rate limits

Most providers do not publish hard rate limits for their public APIs, but
polling faster than 30 seconds is considered impolite and may cause temporary
throttling. The integration enforces:

- **Default interval:** 60 seconds
- **Minimum interval:** 30 seconds
- **Maximum interval:** 3600 seconds (1 hour)
- **Request timeout:** 15 seconds

---

## Sensors

The following sensors are created for each configured status page.
Entity IDs follow the pattern `sensor.statuspage_<page_name>_<sensor_name>`.

### Overall status

| Entity | Type | Possible values |
|--------|------|-----------------|
| `sensor.statuspage_<name>_overall_status` | Enum | `none` · `minor` · `major` · `critical` |

Attributes: `description`, `page_name`, `page_url`, `page_updated_at`

### Active incidents

| Entity | Type | Value |
|--------|------|-------|
| `sensor.statuspage_<name>_active_incidents` | Numeric | Number of unresolved incidents |

Attributes: list of incidents with `name`, `status`, `impact`, `shortlink`,
`started_at`, `updated_at`

### Scheduled maintenances

| Entity | Type | Value |
|--------|------|-------|
| `sensor.statuspage_<name>_scheduled_maintenances` | Numeric | Number of scheduled maintenance windows |

Attributes: list of windows with `name`, `status`, `impact`, `shortlink`,
`scheduled_for`, `scheduled_until`

### Component status (one sensor per component)

| Entity | Type | Possible values |
|--------|------|-----------------|
| `sensor.statuspage_<name>_<component>` | Enum | see table below |

Attributes: `component_id`, `description`, `group`, `group_id`, `updated_at`,
`showcase`

Components are **discovered dynamically**: new components that appear after the
first poll are automatically added as sensors.

---

## Status values and icons

Every sensor has a **dynamic icon** and **icon colour** that reflect the
current status at a glance — no manual template configuration required.

### Overall status (indicator)

| Status | HA value | Icon | Colour |
|--------|----------|------|--------|
| All systems operational | `none` | `mdi:check-circle` | 🟢 green |
| Minor disruption | `minor` | `mdi:alert` | 🟡 yellow |
| Major disruption | `major` | `mdi:alert-circle` | 🟠 orange |
| Critical outage | `critical` | `mdi:close-circle` | 🔴 red |

### Component status

| Status | HA value | Icon | Colour |
|--------|----------|------|--------|
| Fully operational | `operational` | `mdi:check-circle` | 🟢 green |
| Degraded performance | `degraded_performance` | `mdi:alert` | 🟡 yellow |
| Partial outage | `partial_outage` | `mdi:alert-circle` | 🟠 orange |
| Major outage | `major_outage` | `mdi:close-circle` | 🔴 red |
| Under maintenance | `under_maintenance` | `mdi:wrench-clock` | 🔵 blue |

### Icon colours in Lovelace

The integration sets the `icon_color` entity property automatically. Cards
that read this property will colour the icon without any extra configuration.

For **Mushroom Cards**, add this to the `icon_color` field (works in both the
GUI editor and raw YAML mode):

```yaml
icon_color: "{{ state_attr(config.entity, 'icon_color') }}"
```

For the standard **Entity card** with `state_color: true`:

```yaml
type: entities
title: Claude Status
entities:
  - entity: sensor.statuspage_claude_overall_status
    state_color: true
  - entity: sensor.statuspage_claude_active_incidents
    state_color: true
```

---

## Installation

### Manual

1. Download or clone this repository.
2. Copy `custom_components/statuspage_monitor/` to the
   `config/custom_components/` directory of your Home Assistant installation.
3. Restart Home Assistant.

### Via HACS (recommended)

1. Add this repository as a custom repository in HACS (category: **Integration**).
2. Install **Status Page Monitor** through HACS.
3. Restart Home Assistant.

---

## Configuration

### Initial setup

1. Go to **Settings → Devices & Services**.
2. Click **+ Add Integration**.
3. Search for **Status Page Monitor**.
4. Enter the base URL of the status page to monitor
   (e.g. `https://status.claude.com`).
5. Set the polling interval (default: 60 seconds).
6. Click **Submit**. The provider is detected and the page name is fetched
   automatically.

### Multiple status pages

Repeat the steps above for each additional status page. Every page becomes a
separate device in HA with its own set of sensors.

### Changing the polling interval

1. Go to **Settings → Devices & Services → Status Page Monitor**.
2. Click **Configure** next to the desired page.
3. Adjust the interval and click **Save**.

---

## Lovelace example configurations

A ready-to-use card configuration is provided in
[`lovelace_example.yaml`](lovelace_example.yaml).

### Status overview (multiple services)

```yaml
type: entities
title: Service Status
entities:
  - entity: sensor.statuspage_claude_overall_status
    name: Claude (Anthropic)
    state_color: true
  - entity: sensor.statuspage_atlassian_overall_status
    name: Atlassian
    state_color: true
  - entity: sensor.statuspage_github_overall_status
    name: GitHub
    state_color: true
```

### Mushroom cards

```yaml
type: custom:mushroom-entity-card
entity: sensor.statuspage_claude_overall_status
icon_color: "{{ state_attr(config.entity, 'icon_color') }}"
```

### Notification on outage (automation)

```yaml
alias: Notify on Claude outage
trigger:
  - platform: state
    entity_id: sensor.statuspage_claude_overall_status
    from: "none"
condition: []
action:
  - service: notify.mobile_app_my_phone
    data:
      title: "Claude status change"
      message: >
        Status changed to {{ states('sensor.statuspage_claude_overall_status') }}.
        {{ state_attr('sensor.statuspage_claude_overall_status', 'description') }}
```

---

## File structure

```
custom_components/statuspage_monitor/
├── __init__.py              # Integration entry point, setup and teardown
├── manifest.json            # HA integration metadata
├── const.py                 # Constants, normalised status values, icons, colours
├── config_flow.py           # UI config flow (config + options)
├── coordinator.py           # DataUpdateCoordinator, delegates to provider
├── sensor.py                # All sensor entities
├── icon.png                 # Integration icon (256×256)
├── logo.png                 # Integration logo (512×512)
├── strings.json             # UI strings (config flow)
├── providers/
│   ├── __init__.py          # Provider registry and auto-detection
│   ├── base.py              # StatusPageData dataclasses + StatusPageProvider Protocol
│   ├── statuspage_io.py     # ✅ Atlassian Statuspage (statuspage.io) – full implementation
│   ├── status_io.py         # 🔜 Status.io – stub with implementation guide
│   └── uptimerobot.py       # 🔜 UptimeRobot – stub with implementation guide
└── translations/
    ├── en.json              # English translations
    └── nl.json              # Dutch translations
```

---

## License

MIT – see [LICENSE](LICENSE).
