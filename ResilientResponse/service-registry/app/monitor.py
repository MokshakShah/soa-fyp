"""
Background health monitor.

Every HEALTH_CHECK_INTERVAL_SECONDS seconds:
  - Fetch all registered instances from the DB
  - Perform GET <base_url>/health on each
  - Apply state-transition rules (UP / DEGRADED / DOWN / RECOVERING)
  - Persist results to service_health and service_registry

State transition rules
──────────────────────
• UP           → response OK, time < DEGRADED_RESPONSE_MS
• DEGRADED     → response OK, time >= DEGRADED_RESPONSE_MS
• DOWN         → FAILURE_THRESHOLD consecutive failures (no response / error / non-200)
• RECOVERING   → first success after DOWN; stays RECOVERING until RECOVERY_THRESHOLD consecutive successes
"""
import asyncio
import logging
from datetime import datetime
from typing import Dict, Tuple

import httpx

from app.config import (
    HEALTH_CHECK_INTERVAL_SECONDS,
    HEALTH_CHECK_TIMEOUT_SECONDS,
    FAILURE_THRESHOLD,
    RECOVERY_THRESHOLD,
    DEGRADED_RESPONSE_MS,
)
from app.database import get_db
from app.repositories.registry_repo import (
    list_registry,
    update_instance_status,
    upsert_health,
)

logger = logging.getLogger("registry.monitor")

# In-memory counters: (service_name, instance_id) → (consecutive_failures, consecutive_successes)
_counters: Dict[Tuple[str, str], Tuple[int, int]] = {}


def _get_counters(key: Tuple[str, str]) -> Tuple[int, int]:
    return _counters.get(key, (0, 0))


def _set_counters(key: Tuple[str, str], failures: int, successes: int) -> None:
    _counters[key] = (failures, successes)


async def _check_instance(client: httpx.AsyncClient, instance: dict) -> Tuple[str, int | None, str | None, dict | None]:
    """
    Returns (new_status, response_time_ms, error_msg, health_details).
    """
    key = (instance["service_name"], instance["instance_id"])
    failures, successes = _get_counters(key)
    current_status = instance.get("status", "UNKNOWN")
    url = f"{instance['base_url']}/health"

    start = datetime.utcnow()
    try:
        resp = await client.get(url)
        elapsed_ms = int((datetime.utcnow() - start).total_seconds() * 1000)

        if resp.status_code == 200:
            # Success
            failures = 0
            successes += 1
            _set_counters(key, failures, successes)

            # Determine UP vs DEGRADED
            raw_status = "DEGRADED" if elapsed_ms >= DEGRADED_RESPONSE_MS else "UP"

            # Handle RECOVERING transition
            if current_status in ("DOWN", "RECOVERING"):
                if successes >= RECOVERY_THRESHOLD:
                    new_status = raw_status
                    if current_status == "RECOVERING":
                        logger.info(
                            "[recovery] %s/%s is now %s after %d consecutive successes",
                            instance["service_name"], instance["instance_id"], new_status, successes,
                        )
                else:
                    new_status = "RECOVERING"
                    if current_status == "DOWN":
                        logger.info(
                            "[recovering] %s/%s is RECOVERING (success %d/%d)",
                            instance["service_name"], instance["instance_id"], successes, RECOVERY_THRESHOLD,
                        )
            else:
                new_status = raw_status

            try:
                details = resp.json()
            except Exception:
                details = None

            return new_status, elapsed_ms, None, details

        else:
            # Non-200 counts as failure
            error = f"HTTP {resp.status_code}"
            failures += 1
            successes = 0
            _set_counters(key, failures, successes)
            elapsed_ms = int((datetime.utcnow() - start).total_seconds() * 1000)
            new_status = _apply_failure_threshold(current_status, failures, instance)
            return new_status, elapsed_ms, error, None

    except (httpx.RequestError, httpx.TimeoutException) as exc:
        failures += 1
        successes = 0
        _set_counters(key, failures, successes)
        new_status = _apply_failure_threshold(current_status, failures, instance)
        return new_status, None, str(exc), None


def _apply_failure_threshold(current_status: str, failures: int, instance: dict) -> str:
    if failures >= FAILURE_THRESHOLD:
        if current_status != "DOWN":
            logger.warning(
                "[failure] %s/%s → DOWN after %d consecutive failures",
                instance["service_name"], instance["instance_id"], failures,
            )
        return "DOWN"
    # Still within threshold — keep current or mark DEGRADED
    if current_status == "DOWN":
        return "DOWN"
    return current_status if current_status not in ("UNKNOWN",) else "DOWN"


async def run_health_check_cycle() -> None:
    """Perform one full cycle: check every registered instance."""
    db = get_db()
    try:
        instances = await list_registry(db)
    except Exception as exc:
        logger.error("[monitor] Cannot read registry from DB: %s", exc)
        return

    if not instances:
        return

    async with httpx.AsyncClient(timeout=HEALTH_CHECK_TIMEOUT_SECONDS) as client:
        for instance in instances:
            svc = instance["service_name"]
            iid = instance["instance_id"]
            try:
                new_status, rt_ms, error, details = await _check_instance(client, instance)

                # Persist health record
                await upsert_health(db, svc, iid, new_status, rt_ms, error, details)

                # Update registry status + last_heartbeat if UP/RECOVERING/DEGRADED
                heartbeat = datetime.utcnow() if new_status in ("UP", "RECOVERING", "DEGRADED") else None
                await update_instance_status(db, svc, iid, new_status, heartbeat)

                logger.debug(
                    "[check] %s/%s → %s  %s ms",
                    svc, iid, new_status, rt_ms if rt_ms is not None else "timeout",
                )
            except Exception as exc:
                # Never crash the monitor loop on individual instance errors
                logger.error("[monitor] Unexpected error checking %s/%s: %s", svc, iid, exc)


async def monitor_loop() -> None:
    """Long-running background loop. Runs forever until cancelled."""
    logger.info(
        "[monitor] Starting health monitor: interval=%ds, timeout=%ds, failure_threshold=%d, recovery_threshold=%d",
        HEALTH_CHECK_INTERVAL_SECONDS,
        int(HEALTH_CHECK_TIMEOUT_SECONDS),
        FAILURE_THRESHOLD,
        RECOVERY_THRESHOLD,
    )
    while True:
        try:
            await run_health_check_cycle()
        except Exception as exc:
            logger.error("[monitor] Cycle failed: %s", exc)
        await asyncio.sleep(HEALTH_CHECK_INTERVAL_SECONDS)
