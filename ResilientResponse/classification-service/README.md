# Classification Service

Transparent, deterministic, rule-based disaster alert classification.

## Port: 8003

## What it does

Converts a normalized alert payload into a structured classification:
- **disaster_type** — FLOOD | CYCLONE | EARTHQUAKE | LANDSLIDE | CHEMICAL | FIRE | TSUNAMI | VOLCANO | DROUGHT | STORM | UNKNOWN
- **severity** — LOW | MEDIUM | HIGH | CRITICAL
- **confidence** — 0.0–1.0
- **matched_rules** — list of every rule that fired (fully transparent)
- **reason** — human-readable explanation

No LLM, no external AI API, no network calls to classify. All rules are in `app/rules/`.

## API

```
POST /api/classification/classify   — Classify an alert
GET  /health                        — Health check
```

### Request body
```json
{
  "alert_id":    "optional — passed through for tracing",
  "event_type":  "EQ | TC | FL | VO | DR | WF | TS | LS | CH | ST",
  "headline":    "Alert headline or title",
  "description": "Full alert description",
  "severity":    "LOW | MEDIUM | HIGH | CRITICAL | Red | Orange | Green | Extreme | Severe | Moderate | Minor",
  "urgency":     "Immediate | Expected | Future | Past | Unknown",
  "certainty":   "Observed | Likely | Possible | Unlikely | Unknown",
  "affected_area": "Free-text area description",
  "source":      "GDACS | CAP | DEMO"
}
```
All fields are optional. Provide as many as available for better results.

### Response
```json
{
  "alert_id":     "abc-123",
  "disaster_type": "EARTHQUAKE",
  "severity":     "HIGH",
  "confidence":   0.95,
  "matched_rules": ["event_type_code:EQ", "source_severity:high"],
  "reason": "Classified as EARTHQUAKE with HIGH severity (confidence 95%). ..."
}
```

## Classification rules

Rules live in `app/rules/`:
- `disaster_rules.py` — event type codes, keyword matching, confidence scoring
- `severity_rules.py` — source severity mapping, CAP urgency/certainty adjustment, text keywords

To add a new disaster type or keyword: edit `KEYWORD_RULES` in `disaster_rules.py`.

## Run locally

```bash
pip install -r requirements.txt
uvicorn main:app --reload --port 8003
```

## Run tests

```bash
pytest tests/ -v
```

## Environment variables

See `.env.example`
