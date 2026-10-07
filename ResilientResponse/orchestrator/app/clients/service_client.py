"""
HTTP client for downstream services — discovery + PRIMARY/BACKUP failover.
"""
import logging
import time
from typing import Any, Optional

import httpx

from app.discovery import discover_ordered_instances, ServiceUnavailableError

logger = logging.getLogger("orchestrator.client")


class ServiceCallError(Exception):
    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


async def call_service(
    service_name: str,
    method: str,
    path: str,
    *,
    params: Optional[dict] = None,
    json_body: Optional[dict] = None,
    timeout: float = 10.0,
) -> dict[str, Any]:
    """
    Call a downstream service using registry discovery. Tries each healthy instance
    (PRIMARY first, then BACKUP) until one succeeds.
    """
    instances = await discover_ordered_instances(service_name)
    if not instances:
        raise ServiceUnavailableError(f"No healthy instances for {service_name}")

    last_error = "All instances failed"
    last_status: Optional[int] = None
    seen_urls: set[str] = set()

    for inst in instances:
        base = inst["base_url"].rstrip("/")
        if base in seen_urls:
            logger.warning(
                "[client] skipping duplicate instance for %s: %s (%s)",
                service_name, base, inst.get("instance_id"),
            )
            continue
        seen_urls.add(base)
        url = f"{base}{path}"
        logger.info(
            "[client] attempting %s %s via %s (%s)",
            method, path, inst.get("instance_id") or base, service_name,
        )
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.request(method, url, params=params, json=json_body)
        except httpx.RequestError as exc:
            logger.warning(
                "[client] %s %s failed on %s: %s",
                method, path, inst.get("instance_id"), exc,
            )
            last_error = str(exc)
            continue

        if resp.status_code >= 500:
            last_error = f"HTTP {resp.status_code}"
            last_status = resp.status_code
            logger.warning(
                "[client] %s %s → %s on %s",
                method, path, resp.status_code, inst.get("instance_id"),
            )
            continue

        if resp.status_code >= 400:
            detail = resp.text[:200]
            raise ServiceCallError(
                f"{service_name} {path} returned {resp.status_code}: {detail}",
                status_code=resp.status_code,
            )

        if resp.status_code == 204 or not resp.content:
            return {}
        return resp.json()

    logger.error(
        "[client] FAILOVER_EXHAUSTED service=%s path=%s tried=%d last_error=%s",
        service_name, path, len(seen_urls), last_error,
    )
    raise ServiceCallError(
        f"{service_name} unavailable after failover: {last_error}",
        status_code=last_status,
    )


def elapsed_ms(start: float) -> int:
    return int((time.perf_counter() - start) * 1000)
