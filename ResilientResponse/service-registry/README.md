# Service Registry

Tracks all service instances, their health status, and supports primary/backup instance management for future high availability.

## Port: 8008

## Endpoints
- `GET /health` — Health check
- `GET /` — Service info

## Environment Variables
See `.env.example`

## Run Locally
```bash
pip install -r requirements.txt
uvicorn main:app --reload --port 8008
```
