"""
Reverse-proxy router: forwards /api/<resource>/* requests to the correct downstream service.
The API Gateway itself handles /api/auth/* directly.
Everything else is proxied with the Authorization header forwarded.

Phase 12: GET /api/monitoring/summary aggregates health, workflow, and notification
summaries from three backend services in a single gateway-level call.
"""
import asyncio
import logging
from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import Response
import httpx
from app.config import SERVICE_URLS
from app.auth import get_current_admin

logger = logging.getLogger("gateway.proxy")
router = APIRouter(tags=["proxy"])

# Maps the first URL segment after /api/ → service config key
ROUTE_MAP: dict[str, str] = {
    "hospitals":              "hospital-service",
    "police-stations":        "hospital-service",
    "police":                 "hospital-service",
    "resources":              "resource-service",
    "alerts":                 "alert-service",
    "incidents":              "alert-service",
    "workflows":              "orchestrator",
    "routes":                 "route-service",
    "notifications":          "notification-service",
    # Phase 2 compat: /api/services  → service-registry  (returns flat list)
    "services":               "service-registry",
    # Phase 3 registry API
    "registry":               "service-registry",
}


async def _proxy(request: Request, service_url: str, path: str) -> Response:
    url = f"{service_url}/{path}"
    body = await request.body()
    headers = {
        k: v for k, v in request.headers.items()
        if k.lower() not in ("host", "content-length")
    }
    request_timeout = 60.0 if path == "workflows/execute" else 10.0
    attempts = 3 if path == "workflows/execute" else 1
    async with httpx.AsyncClient(timeout=request_timeout) as client:
        for attempt in range(attempts):
            try:
                resp = await client.request(
                    method=request.method,
                    url=url,
                    headers=headers,
                    content=body,
                    params=dict(request.query_params),
                )
            except httpx.RequestError as exc:
                logger.error(f"[proxy] RequestError to {url} on attempt {attempt+1}: {exc}")
                if attempt + 1 == attempts:
                    raise HTTPException(status_code=503, detail=f"Service unavailable: {service_url}")
                await asyncio.sleep(1)
                continue
            if resp.status_code not in (502, 503) or attempt + 1 == attempts:
                break
            await asyncio.sleep(1)
    return Response(
        content=resp.content,
        status_code=resp.status_code,
        headers=dict(resp.headers),
        media_type=resp.headers.get("content-type", "application/json"),
    )


async def _fetch_json(client: httpx.AsyncClient, url: str) -> dict:
    """Fetch JSON from a URL, return empty dict on any error."""
    try:
        resp = await client.get(url, timeout=8.0)
        if resp.status_code == 200:
            return resp.json()
    except Exception as exc:
        logger.warning("[monitoring] fetch failed for %s: %s", url, exc)
    return {}


# ── Phase 12: Monitoring summary aggregation ──────────────────────────────────

@router.get("/api/monitoring/summary")
async def monitoring_summary(
    _admin: dict = Depends(get_current_admin),
):
    """
    Aggregate monitoring summary from three backend services in parallel:
      - Service Registry: instance health counts + per-service breakdown
      - Orchestrator: workflow execution status counts
      - Notification Service: notification delivery status counts

    Returns a single JSON envelope suitable for the admin dashboard.
    Never raises on individual service failures — returns partial data with
    a 'services_available' flag for each source.
    """
    registry_url   = SERVICE_URLS["service-registry"]
    orchestrator_url = SERVICE_URLS["orchestrator"]
    notification_url = SERVICE_URLS["notification-service"]

    async with httpx.AsyncClient(timeout=8.0) as client:
        registry_data, workflow_data, notification_data = await asyncio.gather(
            _fetch_json(client, f"{registry_url}/api/registry/summary"),
            _fetch_json(client, f"{orchestrator_url}/api/workflows/summary"),
            _fetch_json(client, f"{notification_url}/api/notifications/summary"),
        )

    return {
        "registry": {
            "available": bool(registry_data),
            **registry_data,
        },
        "workflows": {
            "available": bool(workflow_data),
            **workflow_data,
        },
        "notifications": {
            "available": bool(notification_data),
            **notification_data,
        },
    }


# ── Generic proxy routes (AFTER specific routes above) ────────────────────────

@router.api_route("/api/{resource}/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_with_path(
    resource: str,
    path: str,
    request: Request,
    _admin: dict = Depends(get_current_admin),
):
    service_key = ROUTE_MAP.get(resource)
    if not service_key:
        raise HTTPException(status_code=404, detail=f"No service mapped for: {resource}")
    service_url = SERVICE_URLS.get(service_key, "")
    return await _proxy(request, service_url, f"api/{resource}/{path}")


@router.api_route("/api/{resource}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_root(
    resource: str,
    request: Request,
    _admin: dict = Depends(get_current_admin),
):
    service_key = ROUTE_MAP.get(resource)
    if not service_key:
        raise HTTPException(status_code=404, detail=f"No service mapped for: {resource}")
    service_url = SERVICE_URLS.get(service_key, "")
    return await _proxy(request, service_url, f"api/{resource}")
