"""Simple Haversine distance — resource-service copy."""
import math
from typing import Optional

EARTH_RADIUS_KM = 6371.0


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lam = math.radians(lon2 - lon1)
    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lam / 2) ** 2
    )
    return EARTH_RADIUS_KM * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def within_radius(
    item_lat: Optional[float],
    item_lon: Optional[float],
    center_lat: float,
    center_lon: float,
    radius_km: float,
) -> bool:
    if item_lat is None or item_lon is None:
        return False
    return haversine_km(center_lat, center_lon, item_lat, item_lon) <= radius_km
