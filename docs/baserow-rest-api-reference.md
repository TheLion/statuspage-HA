# Baserow REST API Referentie

**Datum:** 2026-04-05
**Status:** Fase 2 — gereed voor gebruik in skills (Fase 3)

> ## ⚠️ GEDEELD BESTAND — KOPIE IN MEERDERE PROJECTEN
>
> Dit bestand bestaat in meerdere project-repo's omdat meerdere projecten Baserow gebruiken.
> **Als je dit bestand wijzigt, propageer de wijziging naar ALLE kopieën.**
>
> Bekende locaties (7 kopieën, sync op 2026-04-11):
> - `~/Documents/Apps/BundleVue/docs/baserow-rest-api-reference.md` (authoritative source)
> - `~/Documents/Apps/MotionSense/docs/baserow-rest-api-reference.md`
> - `~/Documents/Apps/ProxmoxVue/docs/baserow-rest-api-reference.md`
> - `~/Documents/Apps/statuspage-HA/docs/baserow-rest-api-reference.md`
> - `~/Documents/Apps/VueSpeed/docs/baserow-rest-api-reference.md`
> - `~/Documents/Apps/Baserow-UI/docs/baserow-rest-api-reference.md`
> - `~/Documents/Apps/GolfCaddy/docs/baserow-rest-api-reference.md`
>
> Projecten die Baserow **niet** gebruiken (geen kopie nodig): `skiprove.com`, `sovrein.nl`.
>
> Sync-commando vanuit BundleVue (na wijziging):
> ```bash
> for target in MotionSense ProxmoxVue statuspage-HA VueSpeed Baserow-UI GolfCaddy; do
>   cp ~/Documents/Apps/BundleVue/docs/baserow-rest-api-reference.md \
>      ~/Documents/Apps/$target/docs/baserow-rest-api-reference.md
> done
> ```
>
> Commit daarna in elk project apart (het zijn aparte git repo's).

---

## Configuratie

| Parameter | Waarde |
|-----------|--------|
| Base URL | `https://baserow.fourpets.net` |
| Table ID (Inbox) | `815` |
| Authenticatie | Database API token via env var `BASEROW_API_TOKEN` |
| Token (huidig) | `DZljfGDG0wpv4HxubAP2xnGzjdpoKRja` ← wordt env var in Fase 3 |

**Token instellen (vereist voor skills):**
```bash
export BASEROW_API_TOKEN="DZljfGDG0wpv4HxubAP2xnGzjdpoKRja"
```

**Waarom Database token (niet JWT):**
- Geen expiry
- Al aanwezig in de skill (file uploads)
- Voldoende voor CRUD op rijen

---

## Endpoint mapping: MCP → REST API

| MCP operatie | REST API endpoint |
|--------------|-------------------|
| `list_table_rows(table_id, ...)` | `GET /api/database/rows/table/{table_id}/` |
| `create_row_table_815(row)` | `POST /api/database/rows/table/815/` |
| `update_row_table_815(id, row)` | `PATCH /api/database/rows/table/815/{id}/` |
| `delete_table_row(table_id, id)` | `DELETE /api/database/rows/table/{table_id}/{id}/` |
| *(niet gebruikt in skills)* | `GET /api/database/fields/table/{table_id}/` |

**Altijd meegeven:** `?user_field_names=true`  
→ Veldnamen zijn dan leesbare strings (bijv. `"project"`) in plaats van `"field_23"`.

---

## Veldwaarden en IDs

### Schrijven (POST/PATCH body) — tekst-waarden

Met `user_field_names=true` accepteert de REST API single-select waarden als **tekst** in de request body:

```json
"status":  "open" | "done" | "idea" | "obsolete"
"type":    "feature" | "backlog" | "decision" | "question"
"project": "BundleVue" | "ProxmoxVue" | "statuspage-HA" | "Baserow Webapp" | "VueSpeed"
"phase":   "Definition" | "MVP" | "Build" | "Scale" | "Polish"
"priority": "low" | "medium" | "high"
```

### Filteren — numerieke IDs vereist

`single_select` filtervelden vereisen het **field ID** in de parameternaam en de **option ID** als waarde. Tekstfilters (tekstvelden) gebruiken ook field IDs maar accepteren tekst als waarde.

| Veld | Field ID | Optie | Option ID |
|------|----------|-------|-----------|
| **project** | 7537 | BundleVue | 3199 |
| | | ProxmoxVue | 3200 |
| | | statuspage-HA | 3201 |
| | | Baserow Webapp | 3209 |
| | | VueSpeed | 3211 |
| **type** | 7519 | feature | 3187 |
| | | backlog | 3188 |
| | | decision | 3189 |
| | | question | 3190 |
| **status** | 7523 | idea | 3191 |
| | | done | 3194 |
| | | open | 3195 |
| | | obsolete | 3208 |
| **phase** | 7538 | Definition | 3203 |
| | | MVP | 3204 |
| | | Build | 3205 |
| | | Scale | 3206 |
| | | Polish | 3207 |
| **priority** | 7524 | low | 3196 |
| | | medium | 3197 |
| | | high | 3198 |

Overige field IDs (tekstvelden — filter met `equal` + tekst-waarde):

| Veld | Field ID |
|------|----------|
| display_name | 7536 |
| source | 7531 |
| search_index | 7539 |
| notion_link | 7533 |
| title | 7521 |

**Link-to-table velden** (`parent_feature`, `depends_on`) — array van ID-objecten:
```json
"parent_feature": [{"id": 123}]
"depends_on": [{"id": 456}, {"id": 789}]
```

**Date veld** — ISO 8601:
```json
"date": "2026-04-05T00:00:00Z"
```

---

## Curl templates

### Standaard headers (herbruikbaar)

```bash
AUTH_HEADER="Authorization: Token ${BASEROW_API_TOKEN}"
CONTENT_HEADER="Content-Type: application/json"
BASE_URL="https://baserow.fourpets.net"
TABLE_ID=815
```

---

### 1. Rijen ophalen (list rows)

> **Belangrijk:** `single_select` filtervelden vereisen de **numerieke option ID** als waarde, en het **field ID** in de parameternaam — niet de veldnaam. Gebruik altijd `filter_type=AND` bij meerdere filters.
>
> Schrijven (POST/PATCH body) werkt wél met tekst-waarden — dit geldt alleen voor filters.

**Basis — filteren op project (BundleVue = option 3199, field 7537):**
```bash
curl -s --show-error \
  -H "${AUTH_HEADER}" \
  "${BASE_URL}/api/database/rows/table/${TABLE_ID}/?user_field_names=true&size=10&filter__field_7537__single_select_equal=3199"
```

**Met type-filter (backlog = option 3188, field 7519):**
```bash
curl -s --show-error \
  -H "${AUTH_HEADER}" \
  "${BASE_URL}/api/database/rows/table/${TABLE_ID}/?user_field_names=true&size=10&filter_type=AND&filter__field_7537__single_select_equal=3199&filter__field_7519__single_select_equal=3188"
```

**Met zoekterm (search — werkt op alle tekstvelden):**
```bash
curl -s --show-error \
  -H "${AUTH_HEADER}" \
  "${BASE_URL}/api/database/rows/table/${TABLE_ID}/?user_field_names=true&size=10&filter_type=AND&filter__field_7537__single_select_equal=3199&search=widget+threshold"
```

**Met project + type + zoekterm (volledig):**
```bash
# PROJECT_OPT en TYPE_OPT zijn numerieke option IDs — zie tabel hieronder
curl -s --show-error \
  -H "${AUTH_HEADER}" \
  "${BASE_URL}/api/database/rows/table/${TABLE_ID}/?user_field_names=true&size=10&filter_type=AND&filter__field_7537__single_select_equal=${PROJECT_OPT}&filter__field_7519__single_select_equal=${TYPE_OPT}&search=${KEYWORDS}"
```

**Paginering (volgende pagina):**
```bash
curl -s --show-error \
  -H "${AUTH_HEADER}" \
  "${BASE_URL}/api/database/rows/table/${TABLE_ID}/?user_field_names=true&size=10&page=2&filter__field_7537__single_select_equal=3199"
```

**Respons verwerken met jq:**
```bash
RESPONSE=$(curl -s --show-error \
  -H "${AUTH_HEADER}" \
  "${BASE_URL}/api/database/rows/table/${TABLE_ID}/?user_field_names=true&size=10&filter__field_7537__single_select_equal=3199")

# Controleer HTTP-succes (jq geeft fout als response leeg/invalid is)
TOTAL=$(echo "${RESPONSE}" | jq '.count')
ROWS=$(echo "${RESPONSE}" | jq '.results')

# Specifiek veld per rij
echo "${RESPONSE}" | jq '.results[] | {id: .id, name: .display_name, status: .status.value}'
```

> **Noot:** Single-select velden komen terug als object: `{"id": 3195, "value": "open"}`. Gebruik `.status.value` om de tekst te lezen.
>
> **Filtersyntax:** `filter__{veldnaam}__{type}=waarde` werkt correct zolang `user_field_names=true` wordt meegestuurd. Field IDs (`filter__field_23__...`) zijn alleen nodig bij veldnamen met speciale tekens — niet van toepassing hier.

**Regels (conform knowledge manager skill):**
- `size` nooit > 20, bij voorkeur ≤ 10
- Altijd eerst filteren op `project`
- Daarna op `type` indien bekend
- Dan zoeken op keywords

---

### 2. Rij aanmaken (create row)

```bash
HTTP_STATUS=$(curl -s --show-error \
  -o /tmp/baserow_create_response.json \
  -w "%{http_code}" \
  -X POST \
  -H "${AUTH_HEADER}" \
  -H "${CONTENT_HEADER}" \
  -d '{
    "display_name": "iOS: Widget drempelwaarde",
    "type": "backlog",
    "project": "BundleVue",
    "phase": "Polish",
    "status": "open",
    "source": "claude",
    "date": "2026-04-05T00:00:00Z",
    "search_index": "widget drempel threshold ios notification",
    "title": "iOS: Widget drempelwaarde"
  }' \
  "${BASE_URL}/api/database/rows/table/${TABLE_ID}/?user_field_names=true")

if [ "${HTTP_STATUS}" != "200" ] && [ "${HTTP_STATUS}" != "201" ]; then
  echo "ERROR: Baserow create mislukt (HTTP ${HTTP_STATUS})"
  cat /tmp/baserow_create_response.json
  exit 1
fi

# Haal het nieuwe row ID op
NEW_ROW_ID=$(cat /tmp/baserow_create_response.json | jq '.id')
echo "Aangemaakt: rij ${NEW_ROW_ID}"
```

**Minimaal vereiste velden bij elke create:**

| Veld | Vereist | Opmerking |
|------|---------|-----------|
| `display_name` | Altijd | Primair label |
| `type` | Altijd | feature / backlog / decision / question |
| `project` | Altijd | BundleVue / ProxmoxVue |
| `phase` | Altijd | Definition / MVP / Build / Scale / Polish |
| `status` | Altijd | Zie type → status mapping |
| `source` | Altijd | "claude" |
| `search_index` | Altijd | 4–6 keywords, lowercase |
| `date` | Sessie-items | ISO 8601, gebruik huidige datum |
| `notion_link` | Alleen als source=Notion | URL naar Notion-pagina |

---

### 3. Rij bijwerken (update row)

```bash
ROW_ID=812

HTTP_STATUS=$(curl -s --show-error \
  -o /tmp/baserow_update_response.json \
  -w "%{http_code}" \
  -X PATCH \
  -H "${AUTH_HEADER}" \
  -H "${CONTENT_HEADER}" \
  -d '{
    "status": "done"
  }' \
  "${BASE_URL}/api/database/rows/table/${TABLE_ID}/${ROW_ID}/?user_field_names=true")

if [ "${HTTP_STATUS}" != "200" ]; then
  echo "ERROR: Baserow update mislukt (HTTP ${HTTP_STATUS})"
  cat /tmp/baserow_update_response.json
  exit 1
fi
```

**Meerdere velden tegelijk:**
```bash
curl -s --show-error \
  -X PATCH \
  -H "${AUTH_HEADER}" \
  -H "${CONTENT_HEADER}" \
  -d '{
    "status": "obsolete",
    "notion_link": "https://www.notion.so/328452a9a8af8169a41df7de32bb19dd"
  }' \
  "${BASE_URL}/api/database/rows/table/${TABLE_ID}/${ROW_ID}/?user_field_names=true"
```

---

### 4. Rij verwijderen (delete row)

```bash
ROW_ID=812

HTTP_STATUS=$(curl -s --show-error \
  -o /dev/null \
  -w "%{http_code}" \
  -X DELETE \
  -H "${AUTH_HEADER}" \
  "${BASE_URL}/api/database/rows/table/${TABLE_ID}/${ROW_ID}/")

if [ "${HTTP_STATUS}" != "204" ]; then
  echo "ERROR: Baserow delete mislukt (HTTP ${HTTP_STATUS})"
  exit 1
fi
```

---

### 5. Bestand uploaden + koppelen (file upload — al in gebruik)

**Stap 1 — Upload:**
```bash
UPLOAD_RESPONSE=$(curl -s --show-error \
  -X POST \
  -H "${AUTH_HEADER}" \
  -F "file=@/tmp/session-summary.md" \
  "${BASE_URL}/api/user-files/upload-file/")

FILE_NAME=$(echo "${UPLOAD_RESPONSE}" | jq -r '.name')
FILE_VISIBLE=$(echo "${UPLOAD_RESPONSE}" | jq -r '.visible_name')
```

**Stap 2 — Bestaande bestanden ophalen:**
```bash
EXISTING_FILES=$(curl -s --show-error \
  -H "${AUTH_HEADER}" \
  "${BASE_URL}/api/database/rows/table/${TABLE_ID}/${ROW_ID}/?user_field_names=true" \
  | jq '.file // []')
```

**Stap 3 — Koppelen aan rij:**
```bash
UPDATED_FILES=$(echo "${EXISTING_FILES}" | jq --arg name "${FILE_NAME}" --arg visible "${FILE_VISIBLE}" \
  '. + [{"name": $name, "visible_name": $visible}]')

curl -s --show-error \
  -X PATCH \
  -H "${AUTH_HEADER}" \
  -H "${CONTENT_HEADER}" \
  -d "{\"file\": ${UPDATED_FILES}}" \
  "${BASE_URL}/api/database/rows/table/${TABLE_ID}/${ROW_ID}/?user_field_names=true"

rm -f /tmp/session-summary.md
```

---

### 6. Velden inspecteren (voor debugging)

```bash
curl -s --show-error \
  -H "${AUTH_HEADER}" \
  "${BASE_URL}/api/database/fields/table/${TABLE_ID}/" \
  | jq '.[] | {id: .id, name: .name, type: .type}'
```

---

## Response-formaat

**List response:**
```json
{
  "count": 42,
  "next": "https://baserow.fourpets.net/api/database/rows/table/815/?page=2",
  "previous": null,
  "results": [
    {
      "id": 812,
      "display_name": "iOS: Widget drempelwaarde",
      "type": {"id": 3188, "value": "backlog"},
      "project": {"id": 3199, "value": "BundleVue"},
      "status": {"id": 3195, "value": "open"},
      "phase": {"id": 3207, "value": "Polish"},
      "search_index": "widget drempel threshold ios notification",
      "date": "2026-04-05T00:00:00Z",
      "source": "claude"
    }
  ]
}
```

**Single-select velden lezen met jq:**
```bash
echo "${RESPONSE}" | jq '.results[] | .status.value'      # "open"
echo "${RESPONSE}" | jq '.results[] | .project.value'     # "BundleVue"
```

---

## Foutafhandeling

| HTTP-code | Betekenis | Actie |
|-----------|-----------|-------|
| 200 / 201 | Succes | Verwerk response |
| 204 | Succes (delete) | Geen body |
| 400 | Validatiefout | Log body, stop |
| 401 | Token ongeldig | Check BASEROW_API_TOKEN |
| 404 | Rij/tabel niet gevonden | Check row_id / table_id |
| 429 | Rate limit | Wacht, retry |
| 5xx | Server error | Log, meld aan gebruiker |

**Standaard foutcheck patroon:**
```bash
if [ "${HTTP_STATUS}" -lt 200 ] || [ "${HTTP_STATUS}" -gt 299 ]; then
  echo "ERROR: Baserow API fout (HTTP ${HTTP_STATUS})"
  exit 1
fi
```

---

## Instructies voor skills (Fase 3)

Skills moeten de volgende conventies hanteren:

1. **Nooit hardcoden** — altijd `${BASEROW_API_TOKEN}`
2. **Altijd** `user_field_names=true` meegeven
3. **Altijd** HTTP-statuscode controleren via `-w "%{http_code}"` + `-o /tmp/...`
4. **Altijd** `--silent --show-error` bij curl
5. **Single-select** als tekst schrijven: `"status": "open"` (niet als ID)
6. **Single-select** bij lezen: `.status.value` (niet `.status`)
7. **Nooit** meer dan 20 rijen ophalen (size ≤ 10 bij voorkeur)
8. **Altijd** filteren op project voordat er gezocht wordt
9. **Bash uitvoeren via Bash tool** — curl is een shell-commando, geen MCP tool
