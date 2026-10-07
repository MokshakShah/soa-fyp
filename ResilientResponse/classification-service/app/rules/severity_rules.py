"""
Severity classification rules.

Inputs considered (all optional):
  source_severity — from alert: LOW | MEDIUM | HIGH | CRITICAL
                               or GDACS: Green | Orange | Red
                               or CAP: Minor | Moderate | Severe | Extreme | Unknown
  urgency         — CAP urgency: Immediate | Expected | Future | Past | Unknown
  certainty       — CAP certainty: Observed | Likely | Possible | Unlikely | Unknown
  text            — combined headline + description (lowercased)

Output: Severity enum + list of rule names that fired
"""
from typing import Tuple, List

from app.models.classification import Severity


# ── Direct source severity mapping ────────────────────────────────────────────

_SOURCE_SEVERITY_MAP = {
    # Our own normalised values
    "critical": Severity.CRITICAL,
    "high":     Severity.HIGH,
    "medium":   Severity.MEDIUM,
    "low":      Severity.LOW,
    # GDACS alert level
    "red":      Severity.CRITICAL,
    "orange":   Severity.HIGH,
    "green":    Severity.MEDIUM,
    # CAP severity field
    "extreme":  Severity.CRITICAL,
    "severe":   Severity.HIGH,
    "moderate": Severity.MEDIUM,
    "minor":    Severity.LOW,
    "unknown":  Severity.MEDIUM,
}

# CAP urgency → severity adjustment (additive score)
_URGENCY_SCORE = {
    "immediate": 2,
    "expected":  1,
    "future":    0,
    "past":     -1,
    "unknown":   0,
}

# CAP certainty → severity adjustment
_CERTAINTY_SCORE = {
    "observed": 2,
    "likely":   1,
    "possible": 0,
    "unlikely":-1,
    "unknown":  0,
}

# Score thresholds → Severity
# Base score comes from source_severity (0–3), plus urgency/certainty adjustments
_SCORE_TO_SEVERITY = [
    (5, Severity.CRITICAL),
    (3, Severity.HIGH),
    (1, Severity.MEDIUM),
    (0, Severity.LOW),
]

# Severity upgrade keywords — if found in text, bump severity by one level
_UPGRADE_KEYWORDS = [
    "life-threatening", "life threatening", "extreme danger",
    "mass casualty", "catastrophic", "major disaster",
    "widespread destruction", "emergency declared",
]

# Severity downgrade keywords
_DOWNGRADE_KEYWORDS = [
    "advisory only", "precautionary", "no casualties reported",
    "minor damage", "low impact",
]

_SEVERITY_ORDER = [Severity.LOW, Severity.MEDIUM, Severity.HIGH, Severity.CRITICAL]


def _bump(sev: Severity, by: int) -> Severity:
    idx = _SEVERITY_ORDER.index(sev)
    return _SEVERITY_ORDER[max(0, min(3, idx + by))]


def evaluate_severity(ctx: dict) -> Tuple[Severity, List[str]]:
    """
    Determine the output severity from available context signals.

    Returns (Severity, fired_rule_names).
    """
    fired: List[str] = []

    source_sev_raw = (ctx.get("source_severity") or "").strip().lower()
    urgency_raw = (ctx.get("urgency") or "").strip().lower()
    certainty_raw = (ctx.get("certainty") or "").strip().lower()
    text = (ctx.get("text") or "").lower()

    # ── Step 1: Base severity from source ─────────────────────────────────────
    base_sev = _SOURCE_SEVERITY_MAP.get(source_sev_raw)
    if base_sev:
        fired.append(f"source_severity:{source_sev_raw}")
    else:
        base_sev = Severity.MEDIUM  # default if nothing provided

    # ── Step 2: CAP urgency/certainty score adjustment ─────────────────────────
    urgency_score = _URGENCY_SCORE.get(urgency_raw, 0)
    certainty_score = _CERTAINTY_SCORE.get(certainty_raw, 0)
    total_adjustment = urgency_score + certainty_score

    if urgency_raw and urgency_raw != "unknown":
        fired.append(f"urgency:{urgency_raw}")
    if certainty_raw and certainty_raw != "unknown":
        fired.append(f"certainty:{certainty_raw}")

    if total_adjustment > 0:
        base_sev = _bump(base_sev, 1)
        fired.append(f"cap_adjustment:+{total_adjustment}")
    elif total_adjustment < -1:
        base_sev = _bump(base_sev, -1)
        fired.append(f"cap_adjustment:{total_adjustment}")

    # ── Step 3: Text-based override ────────────────────────────────────────────
    for kw in _UPGRADE_KEYWORDS:
        if kw in text:
            base_sev = _bump(base_sev, 1)
            fired.append(f"upgrade_keyword:{kw}")
            break  # one upgrade is enough

    for kw in _DOWNGRADE_KEYWORDS:
        if kw in text:
            base_sev = _bump(base_sev, -1)
            fired.append(f"downgrade_keyword:{kw}")
            break

    return base_sev, fired
