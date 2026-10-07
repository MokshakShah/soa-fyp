"""
Classification engine.

Combines disaster-type rules and severity rules to produce a
ClassificationResult from a ClassificationRequest.

This module is the only place that calls both rule sets — keeping the
router thin and rules independently testable.
"""
import logging
from app.models.classification import (
    ClassificationRequest,
    ClassificationResult,
    DisasterType,
    Severity,
)
from app.rules.disaster_rules import evaluate_rules
from app.rules.severity_rules import evaluate_severity

logger = logging.getLogger("classification.engine")


def _build_context(req: ClassificationRequest) -> dict:
    """
    Normalise the request into the flat context dict used by rules.
    Combines headline + description into a single 'text' field.
    """
    parts = []
    if req.headline:
        parts.append(req.headline)
    if req.description:
        parts.append(req.description)
    text = " ".join(parts).lower()

    return {
        "event_type": (req.event_type or "").strip().upper(),
        "text": text,
        "affected_area": (req.affected_area or "").lower(),
        "source": (req.source or "").upper(),
        "source_severity": req.severity or "",
        "urgency": req.urgency or "",
        "certainty": req.certainty or "",
    }


def _build_reason(
    dtype: DisasterType,
    severity: Severity,
    confidence: float,
    disaster_rules: list[str],
    severity_rules: list[str],
    req: ClassificationRequest,
) -> str:
    """
    Construct a human-readable explanation of the classification decision.
    """
    parts = [f"Classified as {dtype.value} with {severity.value} severity (confidence {confidence:.0%})."]

    if disaster_rules:
        parts.append(f"Disaster type determined by: {', '.join(disaster_rules)}.")
    else:
        parts.append("No strong disaster-type signal found; defaulted to UNKNOWN.")

    if severity_rules:
        parts.append(f"Severity determined by: {', '.join(severity_rules)}.")
    else:
        parts.append("Severity defaulted to MEDIUM (no severity signal provided).")

    if req.event_type:
        parts.append(f"Source event type code: {req.event_type}.")

    return " ".join(parts)


def classify(req: ClassificationRequest) -> ClassificationResult:
    """
    Classify a disaster alert using rule-based evaluation.

    Results are deterministic: identical inputs always produce identical outputs.
    No external APIs or ML models are called.
    """
    ctx = _build_context(req)

    # ── Disaster type ─────────────────────────────────────────────────────────
    disaster_type, confidence, disaster_rules = evaluate_rules(ctx)

    # ── Severity ──────────────────────────────────────────────────────────────
    severity, severity_rules = evaluate_severity(ctx)

    # ── Build result ──────────────────────────────────────────────────────────
    all_rules = list(dict.fromkeys(disaster_rules + severity_rules))  # deduplicate, preserve order
    reason = _build_reason(disaster_type, severity, confidence, disaster_rules, severity_rules, req)

    logger.info(
        "Classified alert_id=%s → type=%s severity=%s confidence=%.2f rules=%s",
        req.alert_id, disaster_type.value, severity.value, confidence, all_rules,
    )

    return ClassificationResult(
        alert_id=req.alert_id,
        disaster_type=disaster_type,
        severity=severity,
        confidence=round(confidence, 4),
        matched_rules=all_rules,
        reason=reason,
    )
