"""
Simple Haversine distance calculation.

Used for location-based hospital and police station search.
No external libraries required.
"""
import math
from typing import Optional


EARTH_RADIUS_KM = 6371.0


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Return the great-circle distance in kilometres between two points
    specified by (latitude, longitude) in decimal degrees.
    """
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
    """
    Return True if (item_lat, item_lon) is within radius_km of (center_lat, center_lon).
    Returns False if item coordinates are None.
    """
    if item_lat is None or item_lon is None:
        return False
    return haversine_km(center_lat, center_lon, item_lat, item_lon) <= radius_km
