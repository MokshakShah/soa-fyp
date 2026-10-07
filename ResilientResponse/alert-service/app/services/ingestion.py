"""
Alert ingestion service.

Orchestrates the fetch → normalize → deduplicate → store pipeline.
All adapter interaction is isolated here so the router stays thin.
"""
import logging
from typing import Type

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.adapters.base import AlertSourceAdapter, AdapterError
from app.adapters.gdacs import GDACSAdapter
from app.adapters.demo import DemoAdapter
from app.config import (
    GDACS_FEED_URL, GDACS_TIMEOUT_SECONDS, GDACS_MAX_ALERTS,
    GDACS_COUNTRY, GDACS_TODAY_ONLY, GDACS_REVERSE_GEOCODE,
    GDACS_GEOCODER_URL, ALERT_SOURCE,
)
from app.models.alert import FetchResult
from app.repositories.alert_repo import upsert_alert

logger = logging.getLogger("ingestion")


def get_adapter(source: str | None = None) -> AlertSourceAdapter:
    """
    Return the appropriate adapter based on the source argument or
    the ALERT_SOURCE config value.

    Supported values: GDACS, DEMO
    """
    chosen = (source or ALERT_SOURCE or "GDACS").upper()
    if chosen == "GDACS":
        return GDACSAdapter(
            feed_url=GDACS_FEED_URL,
            timeout=GDACS_TIMEOUT_SECONDS,
            max_alerts=GDACS_MAX_ALERTS,
            country_filter=GDACS_COUNTRY or None,
            today_only=GDACS_TODAY_ONLY,
            reverse_geocode=GDACS_REVERSE_GEOCODE,
            geocoder_url=GDACS_GEOCODER_URL,
        )
    if chosen == "DEMO":
        return DemoAdapter()
    # Unknown source → fall back to DEMO with a warning
    logger.warning("Unknown ALERT_SOURCE '%s', falling back to DEMO adapter", chosen)
    return DemoAdapter()


async def ingest_alerts(
    db: AsyncIOMotorDatabase,
    source: str | None = None,
) -> FetchResult:
    """
    Fetch alerts from the chosen source adapter, deduplicate, and store.

    Returns a FetchResult with counts and any non-fatal error messages.
    Raises AdapterError if the source is completely unreachable (caller
    should return a 503 to the API consumer).
    """
    adapter = get_adapter(source)
    logger.info("Starting ingestion from %s", adapter.source_name)

    # --- Fetch (may raise AdapterError) ---
    normalized_alerts = await adapter.fetch()
    unique_alerts = []
    seen_event_keys: set[str] = set()
    for alert in normalized_alerts:
        event_key = f"{alert.source}:{alert.external_id or alert.title}"
        if event_key in seen_event_keys:
            continue
        seen_event_keys.add(event_key)
        unique_alerts.append(alert)
    if len(unique_alerts) != len(normalized_alerts):
        logger.info(
            "Removed %d duplicate alerts from %s feed",
            len(normalized_alerts) - len(unique_alerts), adapter.source_name,
        )
    normalized_alerts = unique_alerts

    result = FetchResult(
        source=adapter.source_name,
        fetched=len(normalized_alerts),
        created=0,
        updated=0,
        failed=0,
        errors=[],
    )

    # --- Store with deduplication ---
    for alert in normalized_alerts:
        try:
            data = alert.model_dump()
            # Convert enums to strings for MongoDB
            data["severity"] = data["severity"].value if hasattr(data["severity"], "value") else data["severity"]
            data["status"] = data["status"].value if hasattr(data["status"], "value") else data["status"]

            _, was_created = await upsert_alert(db, data)
            if was_created:
                result.created += 1
            else:
                result.updated += 1
        except Exception as exc:
            result.failed += 1
            result.errors.append(str(exc))
            logger.error("Failed to store alert '%s': %s", alert.title, exc)

    logger.info(
        "Ingestion complete: source=%s fetched=%d created=%d updated=%d failed=%d",
        adapter.source_name, result.fetched, result.created, result.updated, result.failed,
    )
    return result
