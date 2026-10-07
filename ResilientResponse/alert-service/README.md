# Alert Service

Receives and stores disaster alerts. Entry point for all incoming emergency alerts into the ResilientResponse platform.

## Port: 8002

## Endpoints
- `GET /health` — Health check
- `GET /` — Service info

## Environment Variables
See `.env.example`

## Run Locally
```bash
pip install -r requirements.txt
uvicorn main:app --reload --port 8002
```
