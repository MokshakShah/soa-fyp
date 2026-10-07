"""
Service Discovery client for the Orchestrator.

The Orchestrator MUST NOT hardcode downstream service URLs.
Instead it calls discover() which asks the Service Registry for a healthy instance.

Usage:
    from app.discovery import discover

    url = await discover("hospital-service")     # raises if unavailable
    resp = await httpx_client.get(f"{url}/api/hospitals")

Discovery rules (enforced by the registry):
  1. Only UP / RECOVERING / DEGRADED instances are considered.
  2. A healthy PRIMARY is preferred over BACKUP.
  3. If no healthy instance exists → ServiceUnavailableError is raised.
"""
import logging
import os
import httpx

logger = logging.getLogger("orchestrator.discovery")


class ServiceUnavailableError(Exception):
    """Raised when no healthy instance is available for a service."""


def _registry_url() -> str:
    return os.getenv("SERVICE_REGISTRY_URL", "http://service-registry:8008")


async def discover(service_name: str, timeout: float = 5.0) -> str:
    """
    Ask the Service Registry for the best available instance of `service_name`.
    Returns the base_url of the selected instance.
    Raises ServiceUnavailableError if no healthy instance is available.
    """
    ordered = await discover_ordered_instances(service_name, timeout=timeout)
    selected = ordered[0]
    logger.debug(
        "[discovery] %s → %s (%s / %s)",
        service_name,
        selected["base_url"],
        selected.get("instance_id"),
        selected.get("instance_role"),
    )
    return selected["base_url"]


def _instance_sort_key(inst: dict) -> tuple:
    """PRIMARY (UP/DEGRADED) before BACKUP; lower response time preferred."""
    role = inst.get("instance_role", "BACKUP")
    status = inst.get("status", "DOWN")
    role_rank = 0 if role == "PRIMARY" else 1
    status_rank = {"UP": 0, "DEGRADED": 1, "RECOVERING": 2}.get(status, 3)
    rtt = inst.get("response_time_ms")
    rtt_rank = rtt if rtt is not None else 99999
    return (role_rank, status_rank, rtt_rank)


async def discover_ordered_instances(service_name: str, timeout: float = 5.0) -> list[dict]:
    """
    Return healthy instances sorted for failover: PRIMARY first, then BACKUP.
    Raises ServiceUnavailableError if none are available.
    """
    url = f"{_registry_url()}/api/registry/discover/{service_name}"
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(url)
    except httpx.RequestError as exc:
        raise ServiceUnavailableError(
            f"Cannot reach Service Registry to discover {service_name}: {exc}"
        )

    if resp.status_code == 503:
        raise ServiceUnavailableError(
            f"No healthy instances available for service: {service_name}"
        )
    if resp.status_code == 404:
        raise ServiceUnavailableError(f"Service not registered: {service_name}")
    if resp.status_code != 200:
        raise ServiceUnavailableError(
            f"Service Registry returned HTTP {resp.status_code} for {service_name}"
        )

    data = resp.json()
    instances = data.get("instances") or []
    if not instances:
        selected = data.get("selected")
        if selected:
            instances = [selected]
    if not instances:
        raise ServiceUnavailableError(
            f"No healthy instances available for service: {service_name}"
        )

    ordered = sorted(instances, key=_instance_sort_key)
    logger.info(
        "[discovery] %s healthy instances=%d selected=%s",
        service_name,
        len(ordered),
        ordered[0].get("instance_id") if ordered else None,
    )
    return ordered


async def discover_all(service_name: str, timeout: float = 5.0) -> list[dict]:
    """
    Return all healthy instances for a service (useful for fan-out operations).
    Returns an empty list if none are available — does NOT raise.
    """
    url = f"{_registry_url()}/api/registry/discover/{service_name}"
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(url)
        if resp.status_code == 200:
            return resp.json().get("instances", [])
    except Exception as exc:
        logger.warning("[discovery] Failed to discover all for %s: %s", service_name, exc)
    return []
