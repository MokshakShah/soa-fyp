"""
Disaster type classification rules.

Each rule is a function that inspects a normalized context dict and returns
(DisasterType, confidence_increment, rule_name) or None if the rule does not fire.

Rules are evaluated in priority order. The first high-confidence match wins.
Multiple lower-confidence matches are accumulated to pick the best type.

Context keys (all optional, lowercased strings):
  event_type    — source event code ("EQ", "TC", "FL", etc.)
  text          — combined headline + description (lowercased)
  affected_area — lowercased affected area description
  source        — alert source name
"""
from typing import Optional, Tuple, List, Dict

from app.models.classification import DisasterType


# Rule return type: (DisasterType, confidence, rule_name)
RuleMatch = Tuple[DisasterType, float, str]


# ── Source event type codes ────────────────────────────────────────────────────

EVENT_TYPE_MAP: Dict[str, Tuple[DisasterType, float]] = {
    "EQ":  (DisasterType.EARTHQUAKE, 0.95),
    "TC":  (DisasterType.CYCLONE,    0.95),
    "FL":  (DisasterType.FLOOD,      0.95),
    "VO":  (DisasterType.VOLCANO,    0.95),
    "DR":  (DisasterType.DROUGHT,    0.95),
    "WF":  (DisasterType.FIRE,       0.95),
    "TS":  (DisasterType.TSUNAMI,    0.95),
    # Less common codes
    "LS":  (DisasterType.LANDSLIDE,  0.90),
    "CH":  (DisasterType.CHEMICAL,   0.90),
    "ST":  (DisasterType.STORM,      0.90),
}


def rule_event_type_code(ctx: dict) -> Optional[RuleMatch]:
    """Match on structured event type code (most reliable signal)."""
    et = (ctx.get("event_type") or "").strip().upper()
    if et in EVENT_TYPE_MAP:
        dtype, conf = EVENT_TYPE_MAP[et]
        return dtype, conf, f"event_type_code:{et}"
    return None


# ── Keyword rules for each disaster type ──────────────────────────────────────
# Format: (keyword_list, DisasterType, confidence, rule_name)
# Keywords are matched against the combined lowercased text.

KEYWORD_RULES: List[Tuple[List[str], DisasterType, float, str]] = [
    # FLOOD
    (["flood", "flooding", "flash flood", "inundation", "riverine", "storm surge", "overflow"],
     DisasterType.FLOOD, 0.80, "keyword:flood"),

    # CYCLONE / HURRICANE / TYPHOON
    (["cyclone", "hurricane", "typhoon", "tropical storm", "tropical cyclone", "wind storm"],
     DisasterType.CYCLONE, 0.80, "keyword:cyclone"),

    # EARTHQUAKE
    (["earthquake", "seismic", "tremor", "aftershock", "epicenter", "magnitude", "richter",
      "quake", "tectonic"],
     DisasterType.EARTHQUAKE, 0.80, "keyword:earthquake"),

    # LANDSLIDE
    (["landslide", "mudslide", "debris flow", "rockfall", "slope failure", "mudflow"],
     DisasterType.LANDSLIDE, 0.80, "keyword:landslide"),

    # CHEMICAL / HAZMAT
    (["chemical", "hazmat", "toxic", "spill", "leak", "contamination", "radiation",
      "nuclear", "biological", "cbrn", "gas leak", "poison"],
     DisasterType.CHEMICAL, 0.80, "keyword:chemical"),

    # FIRE / WILDFIRE
    (["fire", "wildfire", "forest fire", "bushfire", "blaze", "conflagration", "arson"],
     DisasterType.FIRE, 0.80, "keyword:fire"),

    # TSUNAMI
    (["tsunami", "tidal wave", "seismic sea wave"],
     DisasterType.TSUNAMI, 0.85, "keyword:tsunami"),

    # VOLCANO
    (["volcano", "volcanic", "eruption", "lava", "pyroclastic", "ash fall", "caldera"],
     DisasterType.VOLCANO, 0.85, "keyword:volcano"),

    # DROUGHT
    (["drought", "water scarcity", "dry spell", "arid"],
     DisasterType.DROUGHT, 0.75, "keyword:drought"),

    # STORM (generic — lower confidence, only if nothing else matched)
    (["storm", "thunderstorm", "hailstorm", "tornado", "squall", "lightning"],
     DisasterType.STORM, 0.65, "keyword:storm"),
]


def rule_keywords(ctx: dict) -> List[RuleMatch]:
    """Match disaster type keywords in the combined alert text."""
    text = ctx.get("text", "")
    area = ctx.get("affected_area", "")
    combined = f"{text} {area}".lower()
    matches: List[RuleMatch] = []
    for keywords, dtype, conf, name in KEYWORD_RULES:
        for kw in keywords:
            if kw in combined:
                matches.append((dtype, conf, f"{name}[{kw}]"))
                break  # one keyword per rule is enough
    return matches


def rule_gdacs_event_type_in_text(ctx: dict) -> Optional[RuleMatch]:
    """
    Some GDACS events have the event type spelled out in the headline.
    E.g. 'Green earthquake near Japan' → event_type=EQ already handled,
    but 'Red Cyclone HAIKUI' → TC already handled.
    This rule catches event type abbreviations embedded in text.
    """
    text = (ctx.get("text") or "").lower()
    for code, (dtype, conf) in EVENT_TYPE_MAP.items():
        if f" {code.lower()} " in f" {text} ":
            return dtype, conf * 0.85, f"gdacs_code_in_text:{code}"
    return None


# ── Combined evaluation ───────────────────────────────────────────────────────

def evaluate_rules(ctx: dict) -> Tuple[DisasterType, float, List[str]]:
    """
    Run all disaster-type rules and return (best_type, confidence, fired_rules).

    Strategy:
      1. Structured event_type_code has highest priority (0.95).
      2. Keyword matches accumulate per disaster type.
      3. Return the type with the highest accumulated confidence.
      4. If nothing matches → UNKNOWN with confidence 0.0.
    """
    scores: Dict[DisasterType, float] = {}
    fired: List[str] = []

    # Rule 1 — event type code (strong signal, can short-circuit)
    m = rule_event_type_code(ctx)
    if m:
        dtype, conf, name = m
        scores[dtype] = scores.get(dtype, 0.0) + conf
        fired.append(name)

    # Rule 2 — keyword scan (may add to scores or confirm a different type)
    for dtype, conf, name in rule_keywords(ctx):
        scores[dtype] = scores.get(dtype, 0.0) + conf
        fired.append(name)

    # Rule 3 — GDACS code in text (weaker)
    m = rule_gdacs_event_type_in_text(ctx)
    if m:
        dtype, conf, name = m
        scores[dtype] = scores.get(dtype, 0.0) + conf
        fired.append(name)

    if not scores:
        return DisasterType.UNKNOWN, 0.0, []

    # Pick type with highest accumulated score
    best_type = max(scores, key=lambda t: scores[t])
    raw_conf = scores[best_type]

    # Normalise to 0.0–1.0 (cap at 1.0 even if multiple rules fire)
    confidence = min(raw_conf, 1.0)

    # Keep only rules that contributed to the winning type
    winning_rules = [r for r in fired if any(
        dt == best_type and r in fired
        for dt, _, r in (
            [rule_event_type_code(ctx)] if rule_event_type_code(ctx) else []
        ) + rule_keywords(ctx) + (
            [rule_gdacs_event_type_in_text(ctx)] if rule_gdacs_event_type_in_text(ctx) else []
        )
    )]
    # Fallback: return all fired rules if filter produces empty
    if not winning_rules:
        winning_rules = fired

    return best_type, confidence, winning_rules
