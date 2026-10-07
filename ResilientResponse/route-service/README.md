# Route Service

Phase 8 — emergency route calculation (OSRM provider, configurable).

## Port: 8006

## Endpoints
- `POST /api/routes/calculate` — origin/destination → distance, ETA, geometry
- `GET /api/routes/{id}` — persisted route result
- `GET /health`

## Environment
See `.env.example` — `ROUTING_PROVIDER_URL`, `MONGO_URI`, registry settings.

## Tests
```bash
pytest tests/ -v
```
