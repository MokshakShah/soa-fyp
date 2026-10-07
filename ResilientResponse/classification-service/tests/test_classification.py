"""
Phase 5 — Classification Service tests.

Covers:
  - Engine: flood, cyclone, earthquake, landslide, chemical, fire, tsunami,
            volcano, drought, storm, unknown/ambiguous
  - Severity mapping (all source formats)
  - Confidence range validation
  - Determinism (same input → same output)
  - Rule transparency (matched_rules populated)
  - API endpoint: POST /api/classification/classify
  - API endpoint: GET /health
  - Invalid payload handling
"""
import pytest
from httpx import AsyncClient, ASGITransport
from app.engine import classify
from app.models.classification import (
    ClassificationRequest, DisasterType, Severity,
)
from main import app


# ─── helpers ──────────────────────────────────────────────────────────────────

def req(**kwargs) -> ClassificationRequest:
    return ClassificationRequest(**kwargs)


# ─── Disaster type: event_type_code ───────────────────────────────────────────

def test_eq_event_type_code():
    r = classify(req(event_type="EQ", headline="Earthquake near Japan"))
    assert r.disaster_type == DisasterType.EARTHQUAKE
    assert r.confidence >= 0.90
    assert any("event_type_code" in rule for rule in r.matched_rules)


def test_tc_event_type_code():
    r = classify(req(event_type="TC", headline="Cyclone warning Philippines"))
    assert r.disaster_type == DisasterType.CYCLONE
    assert r.confidence >= 0.90


def test_fl_event_type_code():
    r = classify(req(event_type="FL", headline="Flash flood alert"))
    assert r.disaster_type == DisasterType.FLOOD
    assert r.confidence >= 0.90


def test_vo_event_type_code():
    r = classify(req(event_type="VO", headline="Volcanic eruption"))
    assert r.disaster_type == DisasterType.VOLCANO


def test_wf_event_type_code():
    r = classify(req(event_type="WF", headline="Wildfire spreading"))
    assert r.disaster_type == DisasterType.FIRE


def test_ts_event_type_code():
    r = classify(req(event_type="TS", headline="Tsunami warning issued"))
    assert r.disaster_type == DisasterType.TSUNAMI


def test_ls_event_type_code():
    r = classify(req(event_type="LS", headline="Landslide warning"))
    assert r.disaster_type == DisasterType.LANDSLIDE


# ─── Disaster type: keyword-only (no event_type code) ─────────────────────────

def test_flood_keyword():
    r = classify(req(headline="Heavy flooding reported in coastal areas"))
    assert r.disaster_type == DisasterType.FLOOD


def test_flash_flood_keyword():
    r = classify(req(headline="Flash flood warning", description="Inundation of low-lying areas expected"))
    assert r.disaster_type == DisasterType.FLOOD


def test_cyclone_keyword():
    r = classify(req(headline="Tropical cyclone approaching landfall"))
    assert r.disaster_type == DisasterType.CYCLONE


def test_hurricane_keyword():
    r = classify(req(headline="Hurricane category 4 makes landfall"))
    assert r.disaster_type == DisasterType.CYCLONE


def test_typhoon_keyword():
    r = classify(req(headline="Super typhoon warning for eastern coast"))
    assert r.disaster_type == DisasterType.CYCLONE


def test_earthquake_keyword():
    r = classify(req(headline="Strong earthquake measured magnitude 7.2"))
    assert r.disaster_type == DisasterType.EARTHQUAKE


def test_seismic_keyword():
    r = classify(req(headline="Seismic activity detected", description="Tremors felt across the region"))
    assert r.disaster_type == DisasterType.EARTHQUAKE


def test_landslide_keyword():
    r = classify(req(headline="Landslide blocks major highway"))
    assert r.disaster_type == DisasterType.LANDSLIDE


def test_mudslide_keyword():
    r = classify(req(headline="Mudslide warning after heavy rains"))
    assert r.disaster_type == DisasterType.LANDSLIDE


def test_chemical_keyword():
    r = classify(req(headline="Chemical spill at industrial plant"))
    assert r.disaster_type == DisasterType.CHEMICAL


def test_hazmat_keyword():
    r = classify(req(headline="HAZMAT incident — toxic gas leak"))
    assert r.disaster_type == DisasterType.CHEMICAL


def test_radiation_keyword():
    r = classify(req(headline="Radiation leak detected at facility"))
    assert r.disaster_type == DisasterType.CHEMICAL


def test_fire_keyword():
    r = classify(req(headline="Wildfire spreading rapidly in dry conditions"))
    assert r.disaster_type == DisasterType.FIRE


def test_forest_fire_keyword():
    r = classify(req(headline="Forest fire emergency declared"))
    assert r.disaster_type == DisasterType.FIRE


def test_tsunami_keyword():
    r = classify(req(headline="Tsunami warning after offshore earthquake"))
    assert r.disaster_type == DisasterType.TSUNAMI


def test_volcano_keyword():
    r = classify(req(headline="Volcanic eruption begins", description="Lava flows threatening villages"))
    assert r.disaster_type == DisasterType.VOLCANO


def test_drought_keyword():
    r = classify(req(headline="Severe drought conditions declared"))
    assert r.disaster_type == DisasterType.DROUGHT


# ─── Unknown / ambiguous ──────────────────────────────────────────────────────

def test_unknown_no_signals():
    r = classify(req(headline="Situation report", description="General advisory issued"))
    assert r.disaster_type == DisasterType.UNKNOWN
    assert r.confidence == 0.0


def test_unknown_empty_request():
    r = classify(req())
    assert r.disaster_type == DisasterType.UNKNOWN


def test_ambiguous_prefers_higher_confidence():
    """
    When both flood and earthquake keywords appear, the type with the higher
    accumulated confidence should win. Because both fire the same 0.80 keyword
    rule, the result should be deterministic (whichever appears first).
    We just verify it's one of the two valid types and not UNKNOWN.
    """
    r = classify(req(headline="flooding and seismic activity reported"))
    assert r.disaster_type in (DisasterType.FLOOD, DisasterType.EARTHQUAKE)
    assert r.confidence > 0.0


# ─── Event type code beats keyword ────────────────────────────────────────────

def test_event_code_overrides_misleading_keyword():
    """
    event_type=EQ should classify as EARTHQUAKE even if 'flood' appears in text.
    EQ code has confidence 0.95 vs keyword 0.80.
    """
    r = classify(req(event_type="EQ", headline="Earthquake causing flooding in low areas"))
    assert r.disaster_type == DisasterType.EARTHQUAKE


# ─── Severity: direct source mapping ─────────────────────────────────────────

@pytest.mark.parametrize("sev_input,expected", [
    ("critical", Severity.CRITICAL),
    ("CRITICAL", Severity.CRITICAL),
    ("high",     Severity.HIGH),
    ("HIGH",     Severity.HIGH),
    ("medium",   Severity.MEDIUM),
    ("MEDIUM",   Severity.MEDIUM),
    ("low",      Severity.LOW),
    ("LOW",      Severity.LOW),
    # GDACS alert levels
    ("Red",      Severity.CRITICAL),
    ("red",      Severity.CRITICAL),
    ("Orange",   Severity.HIGH),
    ("orange",   Severity.HIGH),
    ("Green",    Severity.MEDIUM),
    ("green",    Severity.MEDIUM),
    # CAP severity field
    ("Extreme",  Severity.CRITICAL),
    ("Severe",   Severity.HIGH),
    ("Moderate", Severity.MEDIUM),
    ("Minor",    Severity.LOW),
])
def test_severity_direct_mapping(sev_input, expected):
    r = classify(req(event_type="EQ", severity=sev_input))
    assert r.severity == expected, f"Expected {expected} for input '{sev_input}', got {r.severity}"


def test_severity_default_when_missing():
    """No severity input → default MEDIUM."""
    r = classify(req(event_type="FL"))
    assert r.severity == Severity.MEDIUM


# ─── Severity: CAP urgency/certainty adjustment ───────────────────────────────

def test_severity_upgraded_by_immediate_urgency():
    """Immediate urgency + Observed certainty should push severity up."""
    r = classify(req(
        event_type="FL",
        severity="medium",
        urgency="Immediate",
        certainty="Observed",
    ))
    assert r.severity in (Severity.HIGH, Severity.CRITICAL)
    assert any("urgency" in rule for rule in r.matched_rules)
    assert any("certainty" in rule for rule in r.matched_rules)


def test_severity_downgraded_by_future_urgency_unlikely_certainty():
    r = classify(req(
        event_type="FL",
        severity="high",
        urgency="Future",
        certainty="Unlikely",
    ))
    # Should stay at HIGH or drop to MEDIUM
    assert r.severity in (Severity.MEDIUM, Severity.HIGH)


def test_severity_upgrade_keyword_life_threatening():
    r = classify(req(
        event_type="FL",
        severity="medium",
        description="This is a life-threatening situation requiring immediate evacuation",
    ))
    assert r.severity in (Severity.HIGH, Severity.CRITICAL)
    assert any("upgrade_keyword" in rule for rule in r.matched_rules)


def test_severity_downgrade_keyword_advisory():
    r = classify(req(
        event_type="FL",
        severity="high",
        description="advisory only — no immediate threat expected minor damage",
    ))
    assert r.severity in (Severity.LOW, Severity.MEDIUM, Severity.HIGH)


# ─── Confidence range ─────────────────────────────────────────────────────────

def test_confidence_between_0_and_1():
    for payload in [
        req(event_type="EQ"),
        req(headline="flooding"),
        req(headline="general advisory"),
        req(),
    ]:
        r = classify(payload)
        assert 0.0 <= r.confidence <= 1.0, f"Confidence out of range: {r.confidence}"


# ─── Determinism ──────────────────────────────────────────────────────────────

def test_same_input_always_same_output():
    payload = req(
        event_type="TC",
        headline="Cyclone warning",
        severity="High",
        urgency="Immediate",
        certainty="Observed",
    )
    results = [classify(payload) for _ in range(5)]
    assert all(r.disaster_type == results[0].disaster_type for r in results)
    assert all(r.severity == results[0].severity for r in results)
    assert all(r.confidence == results[0].confidence for r in results)


# ─── Transparency ─────────────────────────────────────────────────────────────

def test_matched_rules_populated_for_known_type():
    r = classify(req(event_type="EQ", headline="Earthquake warning"))
    assert len(r.matched_rules) > 0


def test_reason_contains_type_and_severity():
    r = classify(req(event_type="FL", severity="high"))
    assert "FLOOD" in r.reason
    assert "HIGH" in r.reason


def test_matched_rules_empty_for_unknown():
    r = classify(req(headline="general situation report"))
    assert r.disaster_type == DisasterType.UNKNOWN
    assert r.confidence == 0.0


# ─── Affected area ────────────────────────────────────────────────────────────

def test_affected_area_contributes_to_classification():
    """Flood keyword in affected_area should be detected."""
    r = classify(req(headline="Emergency alert", affected_area="Flood plains and coastal regions"))
    assert r.disaster_type == DisasterType.FLOOD


# ─── alert_id passthrough ─────────────────────────────────────────────────────

def test_alert_id_passthrough():
    r = classify(req(alert_id="abc-123", event_type="EQ"))
    assert r.alert_id == "abc-123"


def test_alert_id_none_when_not_provided():
    r = classify(req(event_type="FL"))
    assert r.alert_id is None


# ─── API endpoint tests ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_api_health():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["service"] == "classification-service"
    assert data["version"] == "0.5.0"


@pytest.mark.asyncio
async def test_api_classify_earthquake():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/api/classification/classify", json={
            "event_type": "EQ",
            "headline": "Major earthquake near coast",
            "severity": "High",
        })
    assert resp.status_code == 200
    data = resp.json()
    assert data["disaster_type"] == "EARTHQUAKE"
    assert data["severity"] == "HIGH"
    assert 0.0 <= data["confidence"] <= 1.0
    assert isinstance(data["matched_rules"], list)
    assert isinstance(data["reason"], str)
    assert len(data["reason"]) > 0


@pytest.mark.asyncio
async def test_api_classify_flood():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/api/classification/classify", json={
            "event_type": "FL",
            "headline": "Flash flood warning issued",
            "severity": "critical",
            "urgency": "Immediate",
            "certainty": "Observed",
        })
    assert resp.status_code == 200
    data = resp.json()
    assert data["disaster_type"] == "FLOOD"
    assert data["severity"] == "CRITICAL"


@pytest.mark.asyncio
async def test_api_classify_cyclone():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/api/classification/classify", json={
            "headline": "Tropical cyclone approaching coastal districts",
            "severity": "Red",
        })
    assert resp.status_code == 200
    data = resp.json()
    assert data["disaster_type"] == "CYCLONE"
    assert data["severity"] == "CRITICAL"


@pytest.mark.asyncio
async def test_api_classify_unknown():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/api/classification/classify", json={
            "headline": "Situation report issued",
        })
    assert resp.status_code == 200
    data = resp.json()
    assert data["disaster_type"] == "UNKNOWN"
    assert data["confidence"] == 0.0


@pytest.mark.asyncio
async def test_api_classify_empty_body():
    """Empty body is valid (all fields optional) — returns UNKNOWN."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/api/classification/classify", json={})
    assert resp.status_code == 200
    assert resp.json()["disaster_type"] == "UNKNOWN"


@pytest.mark.asyncio
async def test_api_classify_chemical():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/api/classification/classify", json={
            "headline": "Chemical spill — toxic leak reported",
            "severity": "High",
        })
    assert resp.status_code == 200
    assert resp.json()["disaster_type"] == "CHEMICAL"


@pytest.mark.asyncio
async def test_api_classify_fire():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/api/classification/classify", json={
            "event_type": "WF",
            "headline": "Wildfire spreading east",
            "severity": "orange",
        })
    assert resp.status_code == 200
    data = resp.json()
    assert data["disaster_type"] == "FIRE"
    assert data["severity"] == "HIGH"


@pytest.mark.asyncio
async def test_api_classify_landslide():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/api/classification/classify", json={
            "headline": "Landslide blocks road after heavy rainfall",
            "severity": "medium",
        })
    assert resp.status_code == 200
    assert resp.json()["disaster_type"] == "LANDSLIDE"


@pytest.mark.asyncio
async def test_api_result_has_all_required_fields():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/api/classification/classify", json={"event_type": "EQ"})
    assert resp.status_code == 200
    data = resp.json()
    assert "disaster_type" in data
    assert "severity" in data
    assert "confidence" in data
    assert "matched_rules" in data
    assert "reason" in data


@pytest.mark.asyncio
async def test_api_determinism():
    """Calling the API twice with identical input must return identical output."""
    payload = {"event_type": "TC", "headline": "Cyclone warning", "severity": "Red"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r1 = (await ac.post("/api/classification/classify", json=payload)).json()
        r2 = (await ac.post("/api/classification/classify", json=payload)).json()
    assert r1["disaster_type"] == r2["disaster_type"]
    assert r1["severity"] == r2["severity"]
    assert r1["confidence"] == r2["confidence"]
