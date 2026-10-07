"""Service Registry client — classification-service copy."""
import os
import logging
import httpx

logger = logging.getLogger("registry_client")


async def register_with_registry() -> bool:
    registry_url = os.getenv("SERVICE_REGISTRY_URL", "http://service-registry:8008")
    svc_name = os.getenv("SERVICE_NAME", "classification-service")
    svc_instance = os.getenv("SERVICE_INSTANCE_ID", "classification-primary")
    svc_version = os.getenv("SERVICE_VERSION", "0.3.0")
    svc_role = os.getenv("SERVICE_ROLE", "PRIMARY")
    svc_url = os.getenv("SERVICE_BASE_URL", "")

    if not svc_url:
        logger.warning("[registry_client] SERVICE_BASE_URL not set — skipping registration")
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
            resp = await client.post(f"{registry_url}/api/registry/register", json=payload)
            if resp.status_code == 200:
                logger.info("[registry_client] Registered %s/%s (%s)", svc_name, svc_instance, svc_role)
                return True
            logger.warning("[registry_client] HTTP %d", resp.status_code)
            return False
    except Exception as exc:
        logger.warning("[registry_client] Registry unreachable: %s", exc)
        return False
