# Atlassian Statuspage – Home Assistant Integration

Monitor any [Atlassian Statuspage](https://www.atlassian.com/software/statuspage)
from Home Assistant. The integration automatically creates sensors for the
overall status, active incidents, scheduled maintenances, and every individual
component.

Examples of supported status pages:

| Service | URL |
|---------|-----|
| Claude (Anthropic) | https://status.claude.com |
| Atlassian | https://status.atlassian.com |
| GitHub | https://www.githubstatus.com |
| Cloudflare | https://www.cloudflarestatus.com |
| Datadog | https://status.datadoghq.com |
| Twilio | https://status.twilio.com |

> Any service that uses Atlassian Statuspage (hundreds of them) is supported.

---

## How it works

The integration polls the `/api/v2/summary.json` endpoint on a configurable
interval (default 60 s). A single HTTP call returns everything needed:

- Page metadata (name, URL, last updated timestamp)
- Overall status indicator
- Status of every individual component
- Active (unresolved) incidents
- Scheduled maintenance windows

### Why the JSON API and not RSS/Atom or scraping?

| Method | Component status | Structured | Stable |
|--------|:---------------:|:----------:|:------:|
| **JSON API** (chosen) | ✅ | ✅ | ✅ |
| RSS / Atom feed | ❌ (incidents only) | ✅ | ✅ |
| Web scraping | ✅ | ❌ | ❌ |

RSS/Atom feeds only contain incident history, not real-time component status.
Web scraping breaks whenever the HTML changes. The JSON API is the only option
that delivers all required information in a stable, structured format.

### Rate limits

Atlassian does not publish hard rate limits for the public JSON API, but
polling faster than 30 seconds is considered impolite and may result in
temporary IP-level blocking. The integration enforces:

- **Default interval:** 60 seconds
- **Minimum interval:** 30 seconds
- **Maximum interval:** 3600 seconds (1 hour)
- **Request timeout:** 15 seconds

---

## Sensors

The following sensors are created for each configured status page.

### Overall status

| Entity | Type | Possible values |
|--------|------|-----------------|
| `sensor.<name>_overall_status` | Enum | `none` · `minor` · `major` · `critical` |

Attributes: `description`, `page_name`, `page_url`, `page_updated_at`

### Active incidents

| Entity | Type | Value |
|--------|------|-------|
| `sensor.<name>_active_incidents` | Numeric | Number of unresolved incidents |

Attributes: list of incidents with `name`, `status`, `impact`, `shortlink`,
`started_at`, `updated_at`

### Scheduled maintenances

| Entity | Type | Value |
|--------|------|-------|
| `sensor.<name>_scheduled_maintenances` | Numeric | Number of scheduled maintenance windows |

Attributes: list of windows with `name`, `status`, `impact`, `shortlink`,
`scheduled_for`, `scheduled_until`

### Component status (one sensor per component)

| Entity | Type | Possible values |
|--------|------|-----------------|
| `sensor.<name>_<component_id>` | Enum | see table below |

Attributes: `component_id`, `description`, `group`, `group_id`, `updated_at`,
`showcase`

Components are **discovered dynamically**: new components that appear after the
first poll are automatically added as sensors.

---

## Status values and icons

Every sensor has a **dynamic icon** that reflects the current status at a glance.

### Overall status (indicator)

| Status | HA value | Icon |
|--------|----------|------|
| All systems operational | `none` | `mdi:check-circle` |
| Minor disruption | `minor` | `mdi:alert` |
| Major disruption | `major` | `mdi:alert-circle` |
| Critical outage | `critical` | `mdi:close-circle` |

### Component status

| Status | HA value | Icon |
|--------|----------|------|
| Fully operational | `operational` | `mdi:check-circle` |
| Degraded performance | `degraded_performance` | `mdi:alert` |
| Partial outage | `partial_outage` | `mdi:alert-circle` |
| Major outage | `major_outage` | `mdi:close-circle` |
| Under maintenance | `under_maintenance` | `mdi:wrench-clock` |

### Icon colours in Lovelace

HA's Device page does not automatically colour icons for custom sensors — this
is a HA limitation that applies to all third-party integrations.

To get coloured icons in a Lovelace card, add `state_color: true`:

```yaml
type: entities
title: Claude Status
entities:
  - entity: sensor.claude_overall_status
    state_color: true
  - entity: sensor.claude_active_incidents
    state_color: true
  - entity: sensor.claude_scheduled_maintenances
    state_color: true
```

For fully custom colours per state (green / yellow / orange / red), use
[Mushroom Cards](https://github.com/piitaya/lovelace-mushroom):

```yaml
type: custom:mushroom-entity-card
entity: sensor.claude_overall_status
icon_color: >
  {% set s = states('sensor.claude_overall_status') %}
  {% if s == 'none' %} green
  {% elif s == 'minor' %} yellow
  {% elif s == 'major' %} orange
  {% elif s == 'critical' %} red
  {% else %} grey
  {% endif %}
```

The same template pattern works for component sensors with
`operational / degraded_performance / partial_outage / major_outage /
under_maintenance`.

---

## Installation

### Manual

1. Download or clone this repository.
2. Copy `custom_components/atlassian_statuspage/` to the
   `config/custom_components/` directory of your Home Assistant installation.
3. Restart Home Assistant.

### Via HACS (recommended)

1. Add this repository as a custom repository in HACS (category: **Integration**).
2. Install **Atlassian Statuspage** through HACS.
3. Restart Home Assistant.

---

## Configuration

### Initial setup

1. Go to **Settings → Devices & Services**.
2. Click **+ Add Integration**.
3. Search for **Atlassian Statuspage**.
4. Enter the base URL of the status page to monitor
   (e.g. `https://status.claude.com`).
5. Set the polling interval (default: 60 seconds).
6. Click **Submit**. The page name is fetched automatically from the API.

### Multiple status pages

Repeat the steps above for each additional status page. Every page becomes a
separate device in HA with its own set of sensors.

### Changing the polling interval

1. Go to **Settings → Devices & Services → Atlassian Statuspage**.
2. Click **Configure** next to the desired page.
3. Adjust the interval and click **Save**.

---

## Lovelace example configurations

### Status overview (multiple services)

```yaml
type: entities
title: Service Status
entities:
  - entity: sensor.claude_overall_status
    name: Claude (Anthropic)
    state_color: true
  - entity: sensor.atlassian_overall_status
    name: Atlassian
    state_color: true
  - entity: sensor.github_overall_status
    name: GitHub
    state_color: true
```

### Component details with a Markdown card

```yaml
type: markdown
title: Claude – Component Status
content: >
  | Component | Status |
  |-----------|--------|
  {% for entity in states.sensor
     | selectattr('entity_id', 'search', 'claude_')
     | selectattr('entity_id', 'search', '_status')
     | rejectattr('entity_id', 'search', 'overall') %}
  | {{ entity.name }} | {{ entity.state }} |
  {% endfor %}
```

### Notification on outage (automation)

```yaml
alias: Notify on Claude outage
trigger:
  - platform: state
    entity_id: sensor.claude_overall_status
    from: "none"
condition: []
action:
  - service: notify.mobile_app_my_phone
    data:
      title: "Claude status change"
      message: >
        Status changed to {{ states('sensor.claude_overall_status') }}.
        {{ state_attr('sensor.claude_overall_status', 'description') }}
```

---

## File structure

```
custom_components/atlassian_statuspage/
├── __init__.py          # Integration entry point, setup and teardown
├── manifest.json        # HA integration metadata
├── const.py             # Constants, status values and icons
├── config_flow.py       # UI config flow (config + options)
├── coordinator.py       # DataUpdateCoordinator, HTTP polling
├── sensor.py            # All sensor entities
├── strings.json         # UI strings (config flow)
└── translations/
    ├── en.json          # English translations
    └── nl.json          # Dutch translations
```

---

## License

MIT – see [LICENSE](LICENSE).
