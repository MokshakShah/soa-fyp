# Notification Service — Phase 9

Creates, delivers, and tracks emergency notifications for hospitals, police stations, and response teams.

## Port: 8007

## API

```
POST /api/notifications/send        — Create and deliver a notification
GET  /api/notifications             — List (filterable by incident_id, workflow_id, status, recipient_type)
GET  /api/notifications/{id}        — Get single notification
GET  /health                        — Health check (includes provider name)
```

## Notification lifecycle

```
POST /send
  └── persist (status=PENDING)
  └── provider.deliver()
  └── success → mark SENT
  └── failure → mark FAILED (failure_reason persisted)
  └── return final record
```

Provider failure **never causes a 5xx**. The record is returned with `status=FAILED` and `failure_reason` populated.

## Recipient types

`HOSPITAL | POLICE | RESPONSE_TEAM`

## Statuses

`PENDING → SENT | FAILED`

## Provider abstraction

The delivery transport is pluggable:

```
NotificationProvider (ABC)
    └── DemoProvider    — logs to console, always returns success (Phase 9 default)
    └── [SmsProvider]   — add when real SMS is required (Phase 10+)
```

Set `NOTIFICATION_PROVIDER=DEMO` (default) in environment.
To add a new provider: implement `NotificationProvider` in `app/providers/`, add to `factory.py`, set env var.

## MongoDB indexes

`incident_id`, `workflow_id`, `recipient_id`, `status`, `created_at`

## Orchestrator integration

The workflow engine calls `POST /api/notifications/send` via Service Registry discovery.
The step is **non-critical** — failure marks the workflow `PARTIAL`, not `FAILED`.
PRIMARY/BACKUP failover is handled by `call_service()` in the orchestrator.

## Environment variables

See `.env.example`

| Variable | Default | Description |
|---|---|---|
| `NOTIFICATION_PROVIDER` | `DEMO` | Delivery provider (DEMO = log only) |
| `SERVICE_REGISTRY_URL` | `http://service-registry:8008` | Service Registry |
| `MONGO_URI` | `mongodb://mongo:27017/resilientresponse` | MongoDB |

## Run locally

```bash
pip install -r requirements.txt
uvicorn main:app --reload --port 8007
```

## Run tests

```bash
pytest tests/ -v
```
