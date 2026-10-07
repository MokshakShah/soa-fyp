# Orchestrator

Phase 7 workflow engine — receives classified incidents and coordinates emergency response steps across services via Service Registry discovery.

## Port: 8001

## Key endpoints
- `POST /api/workflows/execute` — run workflow for a classified incident
- `GET /api/workflows` — list executions
- `GET /api/workflows/{id}` — detail + events
- `GET /api/workflows/{id}/events` — step history
- `GET /health`

## Supported workflows
FLOOD, CYCLONE, EARTHQUAKE, LANDSLIDE, CHEMICAL, FIRE

## Run tests
```bash
pytest tests/ -v
```
