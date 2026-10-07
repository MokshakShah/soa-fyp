# Hospital Service

Manages hospitals and police stations — Phase 2 CRUD plus Phase 6 operational search and capacity.

## Port: 8004

## Phase 6 Endpoints

### Hospitals
- `GET /api/hospitals/search` — filter by lat/lon/radius, city, min beds, active status
- `POST /api/hospitals/{id}/reserve` — atomically reserve beds (409 if insufficient)
- `POST /api/hospitals/{id}/release` — release beds (capped at emergency_capacity)

### Police
- `GET /api/police-stations/search` — location/city search with status
- `GET /api/police/search` — alias for orchestrator discovery

## Phase 2 Endpoints
- `GET/POST /api/hospitals` — list / create
- `GET/PUT/DELETE /api/hospitals/{id}` — detail / update / delete
- `GET/POST /api/police-stations` — list / create
- `GET/PUT/DELETE /api/police-stations/{id}` — detail / update / delete
- `GET /health` — health check

## Run Locally
```bash
pip install -r requirements.txt
uvicorn main:app --reload --port 8004
```

## Tests
```bash
pytest tests/ -v
```
