<p align="center">
  <img src="brand/logo.png" alt="StatusPage Monitor" width="180">
</p>

<h1 align="center">StatusPage Monitor</h1>

[![Release](https://img.shields.io/github/v/release/TheLion/statuspage-HA?color=blue)](https://github.com/TheLion/statuspage-HA/releases)
[![Installs](https://img.shields.io/badge/dynamic/json?color=41BDF5&logo=home-assistant&label=installs&suffix=%20installs&cacheSeconds=15600&url=https://analytics.home-assistant.io/custom_integrations.json&query=$.statuspage_monitor.total)](https://analytics.home-assistant.io)
[![Last commit](https://img.shields.io/github/last-commit/TheLion/statuspage-HA/statuspage-monitor-main)](https://github.com/TheLion/statuspage-HA/commits/statuspage-monitor-main)
[![Code size](https://img.shields.io/github/languages/code-size/TheLion/statuspage-HA)](https://github.com/TheLion/statuspage-HA)
[![License](https://img.shields.io/github/license/TheLion/statuspage-HA)](LICENSE)

Home Assistant custom integration that monitors status pages and exposes health
data as sensors: overall status, active incidents, scheduled maintenances, and
one sensor per service component.

The provider is **auto-detected from the URL**. Enter the status page address
and the integration handles the rest.


---

## Supported providers

| Provider | Detection | Notes |
|----------|-----------|-------|
| **Atlassian Statuspage** | `/api/v2/summary.json` | The most widely used platform. Covers GitHub, Cloudflare, Atlassian, Anthropic, OpenAI, Twilio, Datadog, and hundreds more |
| **Status.io** | `statuspageId` in page HTML | Two-step: extracts page ID from HTML, then calls the Status.io API |
| **UptimeRobot** | `window.pspApiPath` in page HTML | Monitors + event feed fetched in parallel; overall status derived from worst monitor |
| **Instatus** | `/summary.json` | Hosted platform used by hundreds of services on custom domains or `*.instatus.com` |
| **Better Stack** | `/index.json` | Hosted platform (formerly Better Uptime) used by services like TelemetryDeck and many others on custom domains |
| **Sorry™** | `/api/v1/` | Hosted platform used by services like Moneybird, Broadcom, and Pingdom |
| **Cachet** | `/api/v1/ping` or `/api/ping` | Self-hosted open-source. Supports both v2 (`/api/v1`) and v3 (`/api`) |

### Provider feature comparison

| Feature | Atlassian | Status.io | UptimeRobot | Instatus | Better Stack | Sorry™ | Cachet |
|---------|:---------:|:---------:|:-----------:|:--------:|:------------:|:------:|:------:|
| Overall status | ✅ | ✅ | ✅ (from worst monitor) | ✅ | ✅ | ✅ | ✅ (from worst component) |
| Component sensors | ✅ | ✅ | ✅ (one per monitor) | ✅ | ✅ | ✅ | ✅ |
| Active incidents | ✅ | ✅ | ✅ (from event feed) | ✅ | ✅ | ✅ | ✅ |
| Incident body text | ✅ | ✅ | ✅ | ❌ | ❌ | ✅ | ✅ |
| Scheduled maintenances | ✅ | ✅ | ✅ (from event feed) | ✅ | ✅ | ✅ | ✅ (v2 only) |
| Component groups | ✅ | ❌ | ✅ (monitor groups) | ✅ | ✅ (sections) | ✅ | ✅ |
| Self-hosted | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |

---

## Sensors

Each configured status page gets a dedicated device with the following sensors.
Entity IDs follow the pattern `sensor.statuspage_<page_name>_<sensor>`.

| Sensor | Type | Values / notes |
|--------|------|----------------|
| `_provider_info` | Text | Short provider name (e.g. "Atlassian") |
| `_overall_status` | Enum | `none` · `minor` · `major` · `critical` |
| `_active_incidents` | Count | Number of unresolved incidents. Attribute: `incidents` list |
| `_active_incident_description` | Text | Latest update body of the first active incident. `unknown` when none |
| `_scheduled_maintenances` | Count | Number of upcoming / in-progress windows. Attribute: `maintenances` list |
| `_<component_slug>` | Enum | One per component: `operational` · `degraded_performance` · `partial_outage` · `major_outage` · `under_maintenance` |

Component sensors are **discovered dynamically**. New components that appear
after the first poll are added without a restart.

### Icon and colour attributes

Every sensor exposes two extra attributes that drive dashboard cards:

| Attribute | Example value | Purpose |
|-----------|---------------|---------|
| `icon` | `mdi:alert-circle` | Current MDI icon reflecting the status |
| `icon_color` | `orange` | HA colour name for the icon |

**These attributes only work with Mushroom Cards and auto-entities** (see
[Dashboard cards](#dashboard-cards) below). Standard Lovelace entity cards do
not support dynamic icon colours from attributes.

### Status values and icons

**Overall status / incidents**

| State | `icon` | `icon_color` |
|-------|--------|-------------|
| `none` | `mdi:check-circle` | `green` |
| `minor` | `mdi:alert` | `yellow` |
| `major` | `mdi:alert-circle` | `orange` |
| `critical` | `mdi:close-circle` | `red` |

**Component status**

| State | `icon` | `icon_color` |
|-------|--------|-------------|
| `operational` | `mdi:check-circle` | `green` |
| `degraded_performance` | `mdi:alert` | `yellow` |
| `partial_outage` | `mdi:alert-circle` | `orange` |
| `major_outage` | `mdi:close-circle` | `red` |
| `under_maintenance` | `mdi:wrench-clock` | `blue` |

---

## When the status page changes

Status pages are not static. Components get added, removed, or renamed over
time. The integration handles each scenario as follows:

| Scenario | Behaviour |
|----------|-----------|
| **Component added** | A new sensor is created automatically on the next poll. No restart required. |
| **Component removed** | The sensor becomes `unavailable`. It is not deleted automatically. Remove it manually via **Settings → Devices & Services**. |
| **Component renamed** | The sensor name updates automatically (it reads the name live from the API). The entity ID stays the same: it was assigned at creation time and is not changed by renames. |
| **Page name changed** | Sensor attributes (e.g. `page_name`) update automatically. Existing entity IDs are not affected. |

**Why are removed components not deleted automatically?**
Automatically removing entities would silently break any automations,
dashboards, or scripts that reference them. Keeping the sensor as `unavailable`
makes it visible that something changed, so you can decide what to do.

---

## Dashboard cards

The `icon` and `icon_color` attributes are designed for use with the
**Mushroom Template Card** and **auto-entities**. Both are available via HACS.

Required HACS frontend dependencies:
- [Mushroom](https://github.com/piitaya/lovelace-mushroom)
- [auto-entities](https://github.com/thomasloven/lovelace-auto-entities)

### Show only non-operational components

The card below automatically lists all non-operational and non-idle sensors for
a given status page (e.g. Cloudflare), hiding everything that is `operational`,
`none`, or `unknown`.

```yaml
type: custom:auto-entities
card:
  type: grid
  columns: 1
  square: false
card_param: cards
filter:
  include:
    - options:
        type: custom:mushroom-template-card
        primary: "{{ state_attr(config.entity, 'friendly_name') }}"
        secondary: "{{ states(config.entity) }}"
        icon: "{{ state_attr(config.entity, 'icon') }}"
        icon_color: "{{ state_attr(config.entity, 'icon_color') }}"
      entity_id: sensor.statuspage_cloudflare_*
  exclude:
    - options: {}
      state: operational
    - options: {}
      state: none
    - options: {}
      state: unknown
sort:
  method: friendly_name
```

![Dashboard cards example](docs/dashboard-cards.png)

Change `sensor.statuspage_cloudflare_*` to match your own page slug.

### Single component with colour

```yaml
type: custom:mushroom-template-card
entity: sensor.statuspage_cloudflare_cdn
primary: "{{ state_attr(config.entity, 'friendly_name') }}"
secondary: "{{ states(config.entity) }}"
icon: "{{ state_attr(config.entity, 'icon') }}"
icon_color: "{{ state_attr(config.entity, 'icon_color') }}"
```

### Overall status with description

```yaml
type: custom:mushroom-template-card
entity: sensor.statuspage_cloudflare_overall_status
primary: "{{ state_attr(config.entity, 'page_name') }}"
secondary: "{{ state_attr(config.entity, 'description') }}"
icon: "{{ state_attr(config.entity, 'icon') }}"
icon_color: "{{ state_attr(config.entity, 'icon_color') }}"
```

---

## Installation

### Via HACS (recommended)

1. Open HACS → **Integrations** → three-dot menu → **Custom repositories**.
2. Add `https://github.com/TheLion/statuspage-HA` as an **Integration**.
3. Install **StatusPage Monitor** and restart Home Assistant.

### Manual

1. Copy `custom_components/statuspage_monitor/` into your
   `config/custom_components/` directory.
2. Restart Home Assistant.

### Integration logo

The integration logo is bundled and visible in the HA integrations panel without
any extra setup. HA 2026.3.0+ uses the `brand/` subfolder (new brands proxy API);
older versions fall back to `icon.png` in the integration root (legacy static
file endpoint). No minimum HA version is required.

---

## Configuration

### Add a status page

1. **Settings → Devices & Services → + Add Integration → StatusPage Monitor**
2. Enter the base URL of the status page (e.g. `https://www.cloudflarestatus.com`).
3. Optionally adjust the polling interval (default 60 s, min 30 s, max 3600 s).
4. Submit. The provider is detected and all sensors are created automatically.

Repeat for each additional status page. Every page is an independent device.

### Change the polling interval

**Settings → Devices & Services → StatusPage Monitor → Configure**

### Polling interval and rate limits

The default polling interval is **60 seconds** (minimum 30 s, maximum 3600 s).
This is safe for all supported providers. If you lower the interval, be aware of
the rate limits below — polling too aggressively will result in **HTTP 429
(Too Many Requests)** errors and the integration will temporarily become
unavailable until the limit resets.

The integration handles 429 responses gracefully (automatic backoff), but
prevention is better than recovery.

| Provider | Public API rate limit | Safe minimum interval |
|----------|----------------------|-----------------------|
| **Atlassian Statuspage** | No limit on public Status API | 30 s |
| **Status.io** | No limit on public Status API | 30 s |
| **Instatus** | Not documented | 30 s |
| **Better Stack** | Not documented | 30 s |
| **Sorry™** | 10 requests/second | 30 s |
| **UptimeRobot** | 10 requests/minute (free plan) | 30 s |
| **Cachet** | 300 requests/minute (default, configurable by host) | 30 s |

> **Note:** UptimeRobot's free tier is the most restrictive at 10 req/min.
> At the default 60 s interval the integration uses 1–2 requests per poll
> (depending on the event feed), well within limits. Lowering the interval
> to 30 s is still safe but leaves less headroom.

---

## Examples of compatible status pages

| Service | URL | Provider |
|---------|-----|----------|
| Claude (Anthropic) | https://status.claude.com | Atlassian Statuspage |
| GitHub | https://www.githubstatus.com | Atlassian Statuspage |
| Cloudflare | https://www.cloudflarestatus.com | Atlassian Statuspage |
| iRobot | https://status.irobot.com | Status.io |
| Let's Encrypt | https://letsencrypt.status.io | Status.io |
| Status.io | https://status.status.io | Status.io |
| UptimeRobot | https://status.uptimerobot.com | UptimeRobot |
| iPone | https://status.ipone.nl | UptimeRobot |
| Connectify | https://status.connectify.me | UptimeRobot |
| openSUSE (v2) | https://status.opensuse.org | Cachet |
| Cachet demo (v2) | https://demo.cachethq.io | Cachet |
| Cachet demo (v3) | https://v3.cachethq.io | Cachet |
| Polymarket | https://status.polymarket.com | Instatus |
| Sketch | https://status.sketch.com | Instatus |
| Todoist | https://status.todoist.net | Instatus |
| TelemetryDeck | https://status.telemetrydeck.com | Better Stack |
| Plausible Analytics | https://status.plausible.io | Better Stack |
| Framer | https://status.framer.com | Better Stack |
| Runway | https://status.runway.team | Better Stack |
| Moneybird | https://status.moneybird.com | Sorry™ |
| Broadcom | https://status.broadcom.com | Sorry™ |
| Joinblink | https://status.joinblink.com | Sorry™ |
| Pingdom | https://status.pingdom.com | Sorry™ |

> Atlassian Statuspage is used by hundreds of services (Cloudflare, Datadog,
> Twilio, Atlassian, OpenAI, and many more). Any compatible URL works.
>
> Instatus, Better Stack, and Sorry™ are each used by hundreds of services on
> custom domains. Any compatible URL works.
>
> Cachet is self-hosted, so any self-managed Cachet instance can be monitored
> by entering its base URL. The demo instances above may not always be available.

---

## License

MIT – see [LICENSE](LICENSE).
