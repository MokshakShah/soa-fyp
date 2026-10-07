# ResilientResponse

A pure desktop web-based emergency coordination platform — Final Year Project.

## Current Status: Phase 13 Complete ✅

- ✅ **Final Polish + Release Readiness** — all audit findings resolved, configuration corrected, documentation finalised
- ✅ Service version strings aligned across all `.env.example` files and `docker-compose.yml`
- ✅ `orchestrator/.env.example` HOSPITAL_SERVICE_URL corrected to match actual container name
- ✅ `route-service` docker-compose dependency on MongoDB added (was missing)
- ✅ Healthcheck blocks added to `hospital-backup` and `resource-backup` containers
- ✅ Sidebar version badge and Settings page phase reference updated to current state
- ✅ README workflow curl example corrected to route through API Gateway (port 8000)
- ✅ Incidents and Routes pages now have Refresh buttons for UX consistency
- ✅ **Monitoring + Observability** — live service health, workflow status, and notification delivery visible across the admin UI
- ✅ Structured operational logging across all 9 services
- ✅ Service Registry `/summary` with per-service PRIMARY/BACKUP breakdown
- ✅ API Gateway `GET /api/monitoring/summary` aggregation endpoint
- ✅ Full admin dashboard integration with live persisted backend data
- ✅ API-gateway-only frontend architecture enforced for all admin screens
- ✅ Resilience + PRIMARY/BACKUP failover with automated test coverage

---

## Quick Start

```bash
docker-compose up --build
```

Open: **http://localhost:3000**

Default credentials (development only — change before any deployment):
- Email: `admin@resilientresponse.local`
- Password: `Admin@1234!`

> **Note:** The compose file loads `.env.example` files directly as runtime config, which is intentional for a local development setup. For any deployment, copy each `.env.example` to `.env`, change `JWT_SECRET` and `ADMIN_PASSWORD`, and update the `env_file` references in `docker-compose.yml`.

---

## Services

| Container | Port | Description |
|---|---|---|
| frontend | 3000 | Admin dashboard (Next.js 14) |
| api-gateway | 8000 | JWT auth + reverse proxy to all backend services |
| service-registry | 8008 | Service registration, health monitoring, PRIMARY/BACKUP discovery |
| orchestrator | 8001 | Sequential workflow engine — 8-step disaster response pipeline |
| alert-service | 8002 | Alert ingestion — GDACS RSS, CAP XML, Demo adapters + deduplication |
| classification-service | 8003 | Rule-based disaster classification (stateless, no MongoDB) |
| hospital-primary | 8004 | Hospital/police CRUD + geo-search + bed reservation (PRIMARY) |
| hospital-backup | 8014 | Hospital/police — automatic failover target (BACKUP) |
| resource-primary | 8005 | Emergency resources inventory + allocation (PRIMARY) |
| resource-backup | 8015 | Emergency resources — automatic failover target (BACKUP) |
| route-service | 8006 | Route calculation via OSRM; persists results to MongoDB |
| notification-service | 8007 | Notification dispatch + delivery log (DEMO provider) |

---

## Monitoring + Observability (Phase 12)

### Service Health

The Service Registry health monitor runs every 15 seconds and assigns each instance one of four states:

| State | Meaning |
|---|---|
| UP | Response 200, latency < 2000 ms |
| DEGRADED | Response 200, latency ≥ 2000 ms |
| DOWN | 2 consecutive failures (no response, non-200) |
| RECOVERING | First success after DOWN; stays until 3 consecutive successes |

`GET /api/registry/summary` now returns a full per-service breakdown:

```json
{
  "total_instances": 8,
  "healthy_instances": 7,
  "status_counts": { "UP": 6, "DEGRADED": 1, "DOWN": 1 },
  "services": [
    {
      "service_name": "hospital-service",
      "total_instances": 2,
      "healthy_instances": 2,
      "status_breakdown": { "UP": 2 },
      "instances": [
        { "instance_id": "hospital-primary", "role": "PRIMARY", "status": "UP", "response_time_ms": 42, "last_health_check": "..." },
        { "instance_id": "hospital-backup",  "role": "BACKUP",  "status": "UP", "response_time_ms": 55, "last_health_check": "..." }
      ]
    }
  ]
}
```

### Aggregated Monitoring Summary

`GET /api/monitoring/summary` (API Gateway) fetches three backends in parallel:

```json
{
  "registry":      { "available": true, "total_instances": 8, "healthy_instances": 7, "status_counts": {...}, "services": [...] },
  "workflows":     { "available": true, "total": 42, "running": 1, "completed": 38, "partial": 2, "failed": 1 },
  "notifications": { "available": true, "total": 84, "sent": 80, "failed": 3, "pending": 1 }
}
```

Individual backend failures return `"available": false` for that section only — the endpoint never returns 5xx on partial backend unavailability.

### Structured Logging

All services emit structured log lines for operational events:

```
# Service startup
[startup] Hospital Service started — registry_registered=True

# Health state transitions (service-registry monitor)
[failure]   hospital-service/hospital-primary → DOWN after 2 consecutive failures
[recovering] hospital-service/hospital-primary is RECOVERING (success 1/3)
[recovery]  hospital-service/hospital-primary is now UP after 3 consecutive successes

# Workflow lifecycle (orchestrator engine)
[workflow] START       incident_id=X workflow_id=Y type=FLOOD total_steps=8
[workflow] STEP_START  workflow_id=Y step=3/8 action=reserve_hospital_beds service=hospital-service
[workflow] STEP_OK     workflow_id=Y step=3/8 action=reserve_hospital_beds duration_ms=145
[workflow] STEP_FAIL   workflow_id=Y step=7/8 action=plan_route critical=False duration_ms=5012 error=...
[workflow] PARTIAL     workflow_id=Y incident_id=X
[workflow] COMPLETED   workflow_id=Y incident_id=X
[workflow] FAILED      workflow_id=Y incident_id=X reason=...

# Resource/bed operations
[reserve] OK   hospital_id=X hospital_name=City Hospital beds=5 available_before=20 available_after=15
[allocate] OK  resource_id=X type=RESCUE_VEHICLE quantity=2 available_before=5 available_after=3

# Route provider
[calculate] OK                 incident_id=X distance_km=12.3 travel_min=18.5 provider=OSRM
[calculate] PROVIDER_UNAVAILABLE incident_id=X provider=OSRM error=...

# Notification delivery
[send_service] SENT   notification_id=X provider=DEMO
[send_service] FAILED notification_id=X reason=SMS gateway unreachable
```

No passwords, JWTs, secrets, or sensitive payloads are logged.

---

## Fetch Alerts (via API Gateway)

```bash
# Via API Gateway (authenticated)
POST http://localhost:8000/api/alerts/fetch
Authorization: Bearer <token>

# Or select source
POST http://localhost:8000/api/alerts/fetch?source=DEMO
```

The Alerts page has a "Fetch Alerts" button that triggers this via the UI.

---

## Trigger a workflow (via API Gateway)

All API calls must go through the API Gateway on port 8000. The `/api/workflows` prefix is proxied to the orchestrator automatically.

```bash
POST http://localhost:8000/api/workflows/execute
Authorization: Bearer <token>
Content-Type: application/json

{
  "incident_id": "inc-001",
  "disaster_type": "FLOOD",
  "severity": "HIGH",
  "latitude": 40.7128,
  "longitude": -74.0060,
  "classification": {
    "disaster_type": "FLOOD",
    "severity": "HIGH",
    "confidence": 0.95,
    "reason": "Classified from alert rules"
  }
}
```

---

## Phase 6 Operational APIs

```bash
GET  /api/hospitals/search?lat=&lon=&radius_km=&city=&min_beds=
POST /api/hospitals/{id}/reserve   {"beds": 5}
POST /api/hospitals/{id}/release   {"beds": 5}
GET  /api/police/search?lat=&lon=&radius_km=&city=
GET  /api/police-stations/search   (same as above)
GET  /api/resources/search?type=&lat=&lon=&available_only=
POST /api/resources/{id}/allocate  {"quantity": 2}
POST /api/resources/{id}/release   {"quantity": 2}
```

---

## Run Tests

```bash
cd service-registry     && pytest tests/ -q   # 27  (20 existing + 7 Phase 12)
cd api-gateway          && pytest tests/ -q   # 15  ( 7 existing + 8 Phase 12)
cd alert-service        && pytest tests/ -q   # 31
cd classification-service && pytest tests/ -q # 70
cd hospital-service     && pytest tests/ -q   # 66
cd resource-service     && pytest tests/ -q   # 57
cd orchestrator         && pytest tests/ -q   # 45  (37 existing + 8 Phase 12)
cd route-service        && pytest tests/ -q   #  8
cd notification-service && pytest tests/ -q   # 40  (34 existing + 6 Phase 12)
```

**Total: 359 tests across all 9 services, 0 failures.**

---

## Environment Variables

All configuration is via environment variables. Each service has a `.env.example` template in its directory. The docker-compose file loads these directly for local development.

| Variable | Service | Description |
|---|---|---|
| `MONGO_URI` | all (except classification) | MongoDB connection string |
| `JWT_SECRET` | api-gateway | JWT signing secret — **must be changed for deployment** |
| `JWT_EXPIRE_MINUTES` | api-gateway | Token lifetime in minutes (default 480 = 8 h) |
| `ADMIN_EMAIL` / `ADMIN_PASSWORD` | api-gateway | Seeded admin credentials — **change for deployment** |
| `SERVICE_REGISTRY_URL` | all | URL of the service-registry container |
| `SERVICE_NAME` / `SERVICE_INSTANCE_ID` | all | Registration identity in the registry |
| `SERVICE_ROLE` | hospital, resource | `PRIMARY` or `BACKUP` |
| `SERVICE_BASE_URL` | all | Public URL this instance announces to the registry |
| `ALERT_SOURCE` | alert-service | `GDACS` or `DEMO` |
| `GDACS_FEED_URL` | alert-service | GDACS RSS endpoint |
| `ROUTING_PROVIDER_URL` | route-service | OSRM instance URL |
| `NOTIFICATION_PROVIDER` | notification-service | `DEMO` (log-only); extend for real SMS/email |

---

## Architecture

See [docs/architecture.md](docs/architecture.md).

### Key rules
- Every service is independently deployable
- Adapters convert source-specific formats to NormalizedAlert — nothing else depends on source formats
- Deduplication prevents duplicate records from repeated fetches
- DEMO alerts are always clearly marked — never mixed with real data
- Frontend communicates only through the API Gateway
- Single ADMIN role, desktop-only

---

## Phase Roadmap

| Phase | Status |
|---|---|
| Phase 1 — Foundation | ✅ Complete |
| Phase 2 — Database + Dashboard | ✅ Complete |
| Phase 3 — Service Registry + Discovery | ✅ Complete |
| Phase 4 — Alert Integration (GDACS, CAP, Demo) | ✅ Complete |
| Phase 5 — Classification Service (rule-based) | ✅ Complete |
| Phase 6 — Operational hospital/police/resource services | ✅ Complete |
| Phase 7 — Workflow engine + orchestrator | ✅ Complete |
| Phase 8 — Route service integration | ✅ Complete |
| Phase 9 — Notifications + delivery log | ✅ Complete |
| Phase 10 — Admin dashboard integration | ✅ Complete |
| Phase 11 — Resilience + failover testing | ✅ Complete |
| Phase 12 — Monitoring + Observability | ✅ Complete |
| Phase 13 — Final Polish + Release Readiness | ✅ Complete |
