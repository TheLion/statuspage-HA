# Providers — StatusPage Monitor

> Verplaatst vanuit `CLAUDE.md` op 2026-04-11. CLAUDE.md verwijst naar dit bestand.

## Provider interface

Each provider class in `providers/` must implement:

- `ID: str` — matches constant in `const.py`
- `NAME: str` — full display name
- `SHORT_NAME: str` (optional) — short display name for sensor state
- `SUPPORTS_INCIDENT_BODY: ClassVar[bool]` (default `True`)
- `async def detect(session, url, timeout) -> bool` — return `True` if the URL belongs to this provider
- `async def fetch(session, url, timeout) -> StatusPageData`

## Provider volgorde

De volgorde in `PROVIDERS` in `providers/__init__.py` is belangrijk:

- **Atlassian vóór Instatus** — beide gebruiken `/summary.json`; Atlassian moet eerst worden geprobeerd
- **Cachet als laatste** — vereist een self-hosted ping endpoint

## Nieuwe provider toevoegen

1. Maak `providers/<naam>.py` met `detect()` en `fetch()`
2. Voeg `PROVIDER_<NAAM>` toe aan `const.py`
3. Importeer de klasse in `providers/__init__.py` en voeg hem toe aan `PROVIDERS`
4. Voeg een MDI-fallbackpictogram toe aan `_PROVIDER_ICONS` in `sensor.py`
5. Voeg een SVG-logo toe aan `providers/logos/<naam>.svg`

## Toekomstige providers (onderzocht, nog niet geïmplementeerd)

### Better Stack

- **Website:** https://betterstack.com
- **API:** Voeg `/index.json` toe aan elke status page URL. Geen auth nodig.
- **Formaat:** JSON:API. `data.attributes.aggregate_state`: `operational`, `degraded`, `downtime`, `maintenance`. `included[]` bevat secties, resources (monitors) en status reports (incidents + updates).
- **Detectie:** response bevat `data.type == "status-page"` of `data.attributes.aggregate_state`.
- **Voorbeelden:** Geen bekende publieke URLs gevonden (custom domains, geen vast patroon).

### Hyperping

- **Website:** https://hyperping.com
- **API:** Voeg `/status.json` toe aan elke status page URL. Geen auth nodig.
- **Formaat:** Plat JSON. Top-level `indicator`: `up`, `down`, `outage`, `maintenance`. `services[]` met `name`, `indicator`, `status`.
- **Detectie:** response bevat root-level `indicator` en `services` array.
- **Voorbeelden:** Geen bekende publieke URLs gevonden.

### StatusPal

- **Website:** https://statuspal.io (US) / https://statuspal.eu (EU)
- **API:** Centraal eindpunt (niet op de status page URL zelf):
  - `https://statuspal.io/api/v2/status_pages/{subdomain}/summary`
  - `https://statuspal.eu/api/v2/status_pages/{subdomain}/summary`
- **Formaat:** REST JSON. Bevat status page info, volledige service-hiërarchie, actieve incidenten met timeline-updates, actieve en geplande onderhoudvensters.
- **Detectie:** lastig vanuit de URL — vereist extractie van de subdomain uit de status page HTML of een vaste `*.statuspal.io` / `*.statuspal.eu` URL.
- **Voorbeelden:**
  - https://exoscalestatus.statuspal.eu (Exoscale)

## Niet geschikt / afgevallen

- **Uptime Kuma** — al een uitgebreide bestaande HA-integratie voor.
- **Freshstatus** — stopgezet per 31-03-2026.
- **Cronitor** — alleen RSS, geen JSON API.
- **Upptime** — GitHub-repo per instantie, geen consistent eindpunt.
- **StatusHub** — vereist API-sleutel.
- **Hund** — alleen SSE stream, geen gewone REST polling.
- **OneUptime** — gebruikt POST + statusPageId (niet zichtbaar in URL).
