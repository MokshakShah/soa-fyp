# Resource Service

Tracks emergency resources — Phase 2 CRUD plus Phase 6 search and allocation.

## Port: 8005

## Phase 6 Endpoints
- `GET /api/resources/search` — filter by type, lat/lon/radius, city, availability
- `POST /api/resources/{id}/allocate` — atomically allocate units (409 if unavailable)
- `POST /api/resources/{id}/release` — release units (capped at total quantity)

## Phase 2 Endpoints
- `GET/POST /api/resources` — list / create
- `GET/PUT/DELETE /api/resources/{id}` — detail / update / delete
- `GET /health` — health check

## Run Locally
```bash
pip install -r requirements.txt
uvicorn main:app --reload --port 8005
```

## Tests
```bash
pytest tests/ -v
```
