# API Gateway

Single entry point for all ResilientResponse client requests. Routes requests to appropriate microservices.

## Port: 8000

## Endpoints
- `GET /health` — Health check
- `GET /` — Service info

## Environment Variables
See `.env.example`

## Run Locally
```bash
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```
