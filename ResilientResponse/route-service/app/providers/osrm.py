"""
OSRM routing provider — configurable via ROUTING_PROVIDER_URL.

Does not fabricate route geometry when the provider is unavailable.
"""
import logging
from typing import Any, Optional

import httpx

from app.config import ROUTING_PROVIDER_URL, ROUTING_REQUEST_TIMEOUT

logger = logging.getLogger("route.provider.osrm")


class RoutingProviderError(Exception):
    """External routing provider could not return a route."""


async def fetch_route(
    origin_lat: float,
    origin_lon: float,
    destination_lat: float,
    destination_lon: float,
) -> dict[str, Any]:
    """
    Call OSRM route API. Returns dict with distance_km, duration_minutes, geometry.
    Raises RoutingProviderError on failure.
    """
    base = ROUTING_PROVIDER_URL.rstrip("/")
    # OSRM expects lon,lat order
    path = (
        f"{base}/route/v1/driving/"
        f"{origin_lon},{origin_lat};{destination_lon},{destination_lat}"
        f"?overview=full&geometries=geojson"
    )

    try:
        async with httpx.AsyncClient(timeout=ROUTING_REQUEST_TIMEOUT) as client:
            resp = await client.get(path)
    except httpx.RequestError as exc:
        raise RoutingProviderError(f"Routing provider unreachable: {exc}") from exc

    if resp.status_code != 200:
        raise RoutingProviderError(
            f"Routing provider returned HTTP {resp.status_code}"
        )

    data = resp.json()
    if data.get("code") != "Ok" or not data.get("routes"):
        message = data.get("message") or data.get("code") or "No route found"
        raise RoutingProviderError(f"Routing provider error: {message}")

    route = data["routes"][0]
    distance_m = float(route.get("distance", 0))
    duration_s = float(route.get("duration", 0))
    geometry = _extract_geometry(route.get("geometry"))

    return {
        "distance_km": round(distance_m / 1000.0, 3),
        "estimated_travel_minutes": round(duration_s / 60.0, 2),
        "geometry": geometry,
    }


def _extract_geometry(geo: Optional[dict]) -> Optional[list[list[float]]]:
    if not geo or geo.get("type") != "LineString":
        return None
    coords = geo.get("coordinates")
    if not isinstance(coords, list):
        return None
    # Store as [lat, lon] pairs for readability in API responses
    return [[pt[1], pt[0]] for pt in coords if isinstance(pt, list) and len(pt) >= 2]
