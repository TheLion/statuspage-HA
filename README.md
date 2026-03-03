# Atlassian Statuspage – Home Assistant integratie

Bewaakt elke willekeurige [Atlassian Statuspage](https://www.atlassian.com/software/statuspage) vanuit Home Assistant en maakt voor iedere bewaakt pagina automatisch sensoren aan die meekleuren met de actuele dienststatus.

Voorbeelden van ondersteunde statuspagina's:

| Dienst | URL |
|--------|-----|
| Claude (Anthropic) | https://status.claude.com |
| Atlassian | https://status.atlassian.com |
| GitHub | https://www.githubstatus.com |
| Cloudflare | https://www.cloudflarestatus.com |
| Datadog | https://status.datadoghq.com |
| Twilio | https://status.twilio.com |

> Elke dienst die Atlassian Statuspage gebruikt (honderden) wordt ondersteund.

---

## Werking

De integratie vraagt iedere 60 seconden (instelbaar) het endpoint
`/api/v2/summary.json` op. Dit geeft in **één HTTP-aanroep** alle relevante
informatie terug:

- Paginametadata (naam, URL, tijdstip laatste update)
- Algemene statusindicator
- Status van alle individuele componenten
- Actieve (onopgeloste) incidenten
- Geplande onderhoudsvensters

### Waarom JSON API en niet RSS/Atom of webscraping?

| Methode | Componentstatus | Gestructureerd | Stabiel |
|---------|:--------------:|:--------------:|:-------:|
| **JSON API** (gekozen) | ✅ | ✅ | ✅ |
| RSS / Atom feed | ❌ (alleen incidenten) | ✅ | ✅ |
| Webscraping | ✅ | ❌ | ❌ |

De RSS/Atom-feeds bevatten alleen incidentgeschiedenis, niet de realtime
componentstatus. Webscraping breekt bij HTML-aanpassingen. De JSON API is
de enige optie die alle benodigde informatie stabiel en gestructureerd levert.

### Rate limits

Atlassian publiceert geen harde limieten voor de publieke JSON API, maar
polling sneller dan 30 seconden kan leiden tot tijdelijke IP-blokkering.
De integratie hanteert:

- **Standaard interval:** 60 seconden
- **Minimum interval:** 30 seconden
- **Maximum interval:** 3600 seconden (1 uur)
- **Time-out per aanroep:** 15 seconden

---

## Sensoren

Per geconfigureerde statuspagina worden de volgende sensoren aangemaakt.

### Algemene status

| Entiteit | Sensor type | Mogelijke waarden |
|----------|-------------|-------------------|
| `sensor.<naam>_overall_status` | Enum | `none` · `minor` · `major` · `critical` |

Attributen: `description`, `page_name`, `page_url`, `page_updated_at`

### Actieve incidenten

| Entiteit | Sensor type | Waarde |
|----------|-------------|--------|
| `sensor.<naam>_active_incidents` | Numeriek | Aantal onopgeloste incidenten |

Attributen: lijst van incidenten met `name`, `status`, `impact`, `shortlink`,
`started_at`, `updated_at`

### Geplande onderhoudsvensters

| Entiteit | Sensor type | Waarde |
|----------|-------------|--------|
| `sensor.<naam>_scheduled_maintenances` | Numeriek | Aantal geplande onderhoudsvensters |

Attributen: lijst met `name`, `status`, `impact`, `shortlink`,
`scheduled_for`, `scheduled_until`

### Componentstatus (per component)

| Entiteit | Sensor type | Mogelijke waarden |
|----------|-------------|-------------------|
| `sensor.<naam>_<component_id>` | Enum | zie tabel hieronder |

Attributen: `component_id`, `description`, `group`, `group_id`, `updated_at`,
`showcase`

Componenten worden **dynamisch aangemaakt**: nieuwe componenten die verschijnen
na de eerste poll worden automatisch toegevoegd als sensor.

---

## Statuskleuren en iconen

Elke sensor heeft een **dynamisch icoon** dat direct de status weergeeft.

### Algemene status (indicator)

| Status | HA-waarde | Label | Icoon |
|--------|-----------|-------|-------|
| Alles operationeel | `none` | Operationeel | `mdi:check-circle` |
| Kleine storing | `minor` | Kleine problemen | `mdi:alert` |
| Grote storing | `major` | Grote problemen | `mdi:alert-circle` |
| Kritieke storing | `critical` | Kritiek | `mdi:close-circle` |

### Componentstatus

| Status | HA-waarde | Label | Icoon |
|--------|-----------|-------|-------|
| Volledig operationeel | `operational` | Operationeel | `mdi:check-circle` |
| Verminderde prestaties | `degraded_performance` | Verminderde prestaties | `mdi:alert` |
| Gedeeltelijke storing | `partial_outage` | Gedeeltelijke storing | `mdi:alert-circle` |
| Grote storing | `major_outage` | Grote storing | `mdi:close-circle` |
| In onderhoud | `under_maintenance` | In onderhoud | `mdi:wrench-clock` |

### Icoontint activeren in Lovelace

Voeg `state_color: true` toe aan een Entity-card om de icoontint automatisch
te laten meekleuren:

```yaml
type: entity
entity: sensor.claude_overall_status
state_color: true
```

Of in een Entities-kaart:

```yaml
type: entities
entities:
  - entity: sensor.claude_overall_status
    state_color: true
  - entity: sensor.claude_active_incidents
    state_color: true
```

---

## Installatie

### Handmatig

1. Download of clone deze repository.
2. Kopieer de map `custom_components/atlassian_statuspage/` naar de map
   `config/custom_components/` van uw Home Assistant installatie.
3. Start Home Assistant opnieuw op.

### Via HACS (aanbevolen)

1. Voeg deze repository toe als aangepaste repository in HACS
   (categorie: **Integratie**).
2. Installeer **Atlassian Statuspage** via HACS.
3. Start Home Assistant opnieuw op.

---

## Configuratie

### Eerste keer instellen

1. Ga naar **Instellingen → Apparaten & Diensten**.
2. Klik op **+ Integratie toevoegen**.
3. Zoek naar **Atlassian Statuspage**.
4. Vul de basis-URL in van de te bewaken statuspagina
   (bijv. `https://status.claude.com`).
5. Stel het peilinginterval in (standaard: 60 seconden).
6. Klik op **Verzenden**. De naam wordt automatisch opgehaald uit de API.

### Meerdere statuspagina's

Herhaal stap 1–6 voor elke extra statuspagina. Elke pagina wordt een
afzonderlijk apparaat in HA met eigen sensoren.

### Peilinginterval aanpassen

1. Ga naar **Instellingen → Apparaten & Diensten → Atlassian Statuspage**.
2. Klik op **Configureer** naast de gewenste pagina.
3. Pas het interval aan en klik op **Opslaan**.

---

## Lovelace voorbeeldconfiguraties

### Statusoverzicht (meerdere diensten)

```yaml
type: entities
title: Dienststatus
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

### Componentdetails met Markdown-kaart

```yaml
type: markdown
title: Claude – Componentstatus
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

### Melding bij storing (automatisering)

```yaml
alias: Melding bij Claude-storing
trigger:
  - platform: state
    entity_id: sensor.claude_overall_status
    from: "none"
condition: []
action:
  - service: notify.mobile_app_mijn_telefoon
    data:
      title: "Claude statuswijziging"
      message: >
        Status is veranderd naar
        {{ states('sensor.claude_overall_status') }}.
        {{ state_attr('sensor.claude_overall_status', 'description') }}
```

---

## Bestandsstructuur

```
custom_components/atlassian_statuspage/
├── __init__.py          # Integratie-entry point, setup en teardown
├── manifest.json        # HA-integratiemetadata
├── const.py             # Constanten, statuswaarden en iconen
├── config_flow.py       # UI-configuratiestroom (config + opties)
├── coordinator.py       # DataUpdateCoordinator, HTTP-polling
├── sensor.py            # Alle sensorentiteiten
├── strings.json         # UI-teksten (config flow)
└── translations/
    ├── en.json          # Engelse vertalingen
    └── nl.json          # Nederlandse vertalingen
```

---

## Licentie

MIT – zie [LICENSE](LICENSE).
