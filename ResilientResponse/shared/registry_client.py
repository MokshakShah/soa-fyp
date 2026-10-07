"""
Shared Service Registry client.

Each service imports this module and calls `register_with_registry()` in its
lifespan startup.  All configuration is read from environment variables so
no URLs are hardcoded in application logic.

Environment variables expected by every service:
  SERVICE_NAME          – logical service name  e.g. "hospital-service"
  SERVICE_INSTANCE_ID   – unique instance id     e.g. "hospital-primary"
  SERVICE_VERSION       – semver string           e.g. "0.3.0"
  SERVICE_ROLE          – PRIMARY | BACKUP        e.g. "PRIMARY"
  SERVICE_BASE_URL      – this instance's URL     e.g. "http://hospital-primary:8004"
  SERVICE_REGISTRY_URL  – registry base URL       e.g. "http://service-registry:8008"
"""
import os
import logging
import httpx

logger = logging.getLogger("registry_client")

REGISTRY_URL = os.getenv("SERVICE_REGISTRY_URL", "http://service-registry:8008")
REGISTER_ENDPOINT = f"{REGISTRY_URL}/api/registry/register"


async def register_with_registry(
    service_name: str | None = None,
    instance_id: str | None = None,
    base_url: str | None = None,
    version: str | None = None,
    role: str | None = None,
) -> bool:
    """
    Register this service instance with the Service Registry.
    Falls back to environment variables when arguments are not provided.

    Returns True on success, False on failure (so callers can log but not crash).
    """
    svc_name = service_name or os.getenv("SERVICE_NAME", "unknown-service")
    svc_instance = instance_id or os.getenv("SERVICE_INSTANCE_ID", f"{svc_name}-primary")
    svc_version = version or os.getenv("SERVICE_VERSION", "0.3.0")
    svc_role = role or os.getenv("SERVICE_ROLE", "PRIMARY")
    svc_url = base_url or os.getenv("SERVICE_BASE_URL", "")

    if not svc_url:
        logger.warning("[registry_client] SERVICE_BASE_URL not set for %s — skipping registration", svc_name)
        return False

    payload = {
        "service_name": svc_name,
        "instance_id": svc_instance,
        "base_url": svc_url,
        "version": svc_version,
        "instance_role": svc_role.upper(),
    }

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(REGISTER_ENDPOINT, json=payload)
            if resp.status_code == 200:
                logger.info(
                    "[registry_client] Registered: service=%s instance=%s role=%s",
                    svc_name, svc_instance, svc_role,
                )
                return True
            else:
                logger.warning(
                    "[registry_client] Registration returned HTTP %d for %s/%s",
                    resp.status_code, svc_name, svc_instance,
                )
                return False
    except Exception as exc:
        logger.warning(
            "[registry_client] Could not reach registry for %s/%s: %s (service will still start)",
            svc_name, svc_instance, exc,
        )
        return False
