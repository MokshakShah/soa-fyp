"""
Classification router — exposes POST /api/classification/classify
"""
import logging
import time
from fastapi import APIRouter, HTTPException

from app.models.classification import ClassificationRequest, ClassificationResult
from app.engine import classify

logger = logging.getLogger("router.classification")
router = APIRouter(prefix="/api/classification", tags=["classification"])


@router.post("/classify", response_model=ClassificationResult)
async def classify_alert(body: ClassificationRequest):
    """
    Classify a disaster alert using transparent rule-based logic.

    Accepts a normalized alert payload and returns:
    - disaster_type  — FLOOD | CYCLONE | EARTHQUAKE | LANDSLIDE | CHEMICAL | FIRE | TSUNAMI | VOLCANO | DROUGHT | STORM | UNKNOWN
    - severity       — LOW | MEDIUM | HIGH | CRITICAL
    - confidence     — 0.0–1.0
    - matched_rules  — list of rule names that fired
    - reason         — human-readable explanation

    Results are deterministic: same input always produces same output.
    No external AI or LLM is used.
    """
    start = time.perf_counter()
    try:
        result = classify(body)
        duration_ms = int((time.perf_counter() - start) * 1000)
        logger.info(
            "[classify] disaster_type=%s severity=%s confidence=%.2f duration_ms=%d",
            result.disaster_type, result.severity, result.confidence, duration_ms,
        )
        return result
    except Exception as exc:
        logger.error("Classification error: %s", exc)
        raise HTTPException(status_code=500, detail="Classification failed")
