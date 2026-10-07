"""
Phase 4 — Adapter tests.

Covers:
  - Normalized alert model validation
  - GDACS XML parsing (valid, malformed, empty)
  - CAP XML parsing (valid, non-Actual status, missing fields)
  - Demo adapter
  - Deduplication in alert_repo
  - API endpoints: list, detail, demo, fetch
  - External provider failure handling
"""
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from httpx import AsyncClient, ASGITransport

from main import app

# ─── helpers ──────────────────────────────────────────────────────────────────

MINIMAL_GDACS_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"
     xmlns:gdacs="http://www.gdacs.org"
     xmlns:geo="http://www.w3.org/2003/01/geo/wgs84_pos#"
     xmlns:dc="http://purl.org/dc/elements/1.1/">
  <channel>
    <title>GDACS</title>
    <item>
      <title>Green earthquake near Japan</title>
      <description>M6.1 earthquake</description>
      <link>https://www.gdacs.org/report.aspx?eventid=1000001&amp;episodeid=1</link>
      <pubDate>Mon, 01 Jan 2024 12:00:00 +0000</pubDate>
      <gdacs:eventtype>EQ</gdacs:eventtype>
      <gdacs:alertlevel>Green</gdacs:alertlevel>
      <gdacs:eventid>1000001</gdacs:eventid>
      <gdacs:episodeid>1</gdacs:episodeid>
      <gdacs:country>Japan</gdacs:country>
      <geo:lat>35.6762</geo:lat>
      <geo:long>139.6503</geo:long>
    </item>
    <item>
      <title>Orange Cyclone in Philippines</title>
      <description>Strong cyclone approaching</description>
      <link>https://www.gdacs.org/report.aspx?eventid=1000002&amp;episodeid=2</link>
      <pubDate>Mon, 01 Jan 2024 13:00:00 +0000</pubDate>
      <gdacs:eventtype>TC</gdacs:eventtype>
      <gdacs:alertlevel>Orange</gdacs:alertlevel>
      <gdacs:eventid>1000002</gdacs:eventid>
      <gdacs:episodeid>2</gdacs:episodeid>
      <gdacs:country>Philippines</gdacs:country>
      <geo:lat>14.5995</geo:lat>
      <geo:long>120.9842</geo:long>
    </item>
  </channel>
</rss>"""

MINIMAL_CAP_XML = """<?xml version="1.0" encoding="UTF-8"?>
<alert xmlns="urn:oasis:names:tc:emergency:cap:1.2">
  <identifier>TEST-CAP-001</identifier>
  <sender>test@example.gov</sender>
  <sent>2024-01-01T10:00:00</sent>
  <status>Actual</status>
  <msgType>Alert</msgType>
  <scope>Public</scope>
  <info>
    <language>en</language>
    <category>Geo</category>
    <event>Earthquake Warning</event>
    <urgency>Immediate</urgency>
    <severity>Severe</severity>
    <certainty>Observed</certainty>
    <effective>2024-01-01T10:00:00</effective>
    <expires>2024-01-01T16:00:00</expires>
    <headline>Major earthquake warning for test region</headline>
    <description>A major earthquake has been detected.</description>
    <web>https://example.gov/alert/001</web>
    <area>
      <areaDesc>Test Region</areaDesc>
      <circle>35.6762,139.6503 50</circle>
    </area>
  </info>
</alert>"""

CAP_NON_ACTUAL = """<?xml version="1.0" encoding="UTF-8"?>
<alert xmlns="urn:oasis:names:tc:emergency:cap:1.2">
  <identifier>TEST-CAP-002</identifier>
  <sender>test@example.gov</sender>
  <sent>2024-01-01T10:00:00</sent>
  <status>Test</status>
  <msgType>Alert</msgType>
  <scope>Public</scope>
  <info>
    <category>Geo</category>
    <event>Test Event</event>
    <urgency>Unknown</urgency>
    <severity>Unknown</severity>
    <certainty>Unknown</certainty>
    <headline>This is a test</headline>
  </info>
</alert>"""

MALFORMED_XML = "<this is not valid xml"


# ─── Normalized alert model ───────────────────────────────────────────────────

def test_normalized_alert_requires_title():
    from app.models.alert import NormalizedAlert
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        NormalizedAlert(source="DEMO", disaster_type="FLOOD")  # title missing


def test_normalized_alert_default_severity():
    from app.models.alert import NormalizedAlert, AlertSeverity
    alert = NormalizedAlert(source="DEMO", title="Test", disaster_type="FLOOD")
    assert alert.severity == AlertSeverity.MEDIUM


def test_normalized_alert_default_status():
    from app.models.alert import NormalizedAlert, AlertStatus
    alert = NormalizedAlert(source="DEMO", title="Test", disaster_type="FLOOD")
    assert alert.status == AlertStatus.NEW


def test_normalized_alert_full_fields():
    from app.models.alert import NormalizedAlert, AlertSeverity, AlertStatus
    alert = NormalizedAlert(
        external_id="EXT-001",
        source="GDACS",
        title="Flood Warning",
        disaster_type="FLOOD",
        severity=AlertSeverity.HIGH,
        location_name="Test City",
        latitude=12.34,
        longitude=56.78,
    )
    assert alert.external_id == "EXT-001"
    assert alert.source == "GDACS"
    assert alert.severity == AlertSeverity.HIGH


# ─── GDACS adapter ────────────────────────────────────────────────────────────

def test_gdacs_parse_valid_feed():
    from app.adapters.gdacs import parse_gdacs_feed
    alerts = parse_gdacs_feed(MINIMAL_GDACS_RSS)
    assert len(alerts) >= 1
    assert alerts[0].source == "GDACS"
    assert alerts[0].disaster_type == "EARTHQUAKE"
    assert alerts[0].location_name == "Japan"
    assert alerts[0].latitude == pytest.approx(35.6762)
    assert alerts[0].longitude == pytest.approx(139.6503)
    assert alerts[0].external_id is not None
    assert alerts[0].external_id.startswith("GDACS-")
    assert alerts[0].external_id == "GDACS-EQ-1000001"


def test_gdacs_parse_severity_mapping():
    from app.adapters.gdacs import parse_gdacs_feed
    from app.models.alert import AlertSeverity
    alerts = parse_gdacs_feed(MINIMAL_GDACS_RSS)
    # First alert has Green → MEDIUM
    assert alerts[0].severity == AlertSeverity.MEDIUM


def test_gdacs_parse_country_filter():
    from app.adapters.gdacs import parse_gdacs_feed
    assert parse_gdacs_feed(MINIMAL_GDACS_RSS, country_filter="India") == []
    assert len(parse_gdacs_feed(MINIMAL_GDACS_RSS, country_filter="Japan")) == 1


def test_gdacs_country_filter_accepts_regional_india_label():
    from app.adapters.gdacs import parse_gdacs_feed
    regional_feed = MINIMAL_GDACS_RSS.replace("<gdacs:country>Japan</gdacs:country>", "<gdacs:country>Southern India</gdacs:country>")
    alerts = parse_gdacs_feed(regional_feed, country_filter="India")
    assert len(alerts) == 1
    assert alerts[0].location_name == "Southern India"


def test_gdacs_publication_date_filter_keeps_only_current_day():
    from datetime import date
    from app.adapters.gdacs import parse_gdacs_feed

    assert len(parse_gdacs_feed(MINIMAL_GDACS_RSS, published_on=date(2024, 1, 1))) == 2
    assert parse_gdacs_feed(MINIMAL_GDACS_RSS, published_on=date(2024, 1, 2)) == []


def test_gdacs_same_event_dedupes_across_episodes():
    from app.adapters.gdacs import parse_gdacs_feed

    first_item = MINIMAL_GDACS_RSS.split("    <item>\n", 1)[1].split("    </item>", 1)[0]
    duplicate = (
        "    <item>\n"
        + first_item.replace("episodeid=1", "episodeid=99")
        .replace("<gdacs:episodeid>1</gdacs:episodeid>", "<gdacs:episodeid>99</gdacs:episodeid>")
        + "    </item>\n"
    )
    xml = MINIMAL_GDACS_RSS.replace("  </channel>", duplicate + "  </channel>")

    alerts = parse_gdacs_feed(xml)
    assert len(alerts) == 2


def test_gdacs_parse_malformed_xml():
    from app.adapters.gdacs import parse_gdacs_feed
    from app.adapters.base import AdapterError
    with pytest.raises(AdapterError):
        parse_gdacs_feed(MALFORMED_XML)


def test_gdacs_parse_empty_channel():
    xml = """<?xml version="1.0"?><rss version="2.0"><channel></channel></rss>"""
    from app.adapters.gdacs import parse_gdacs_feed
    alerts = parse_gdacs_feed(xml)
    assert alerts == []


@pytest.mark.asyncio
async def test_gdacs_adapter_network_timeout():
    """Network timeout → AdapterError, not a crash."""
    import httpx
    from app.adapters.gdacs import GDACSAdapter
    from app.adapters.base import AdapterError
    adapter = GDACSAdapter(feed_url="http://fake.gdacs.example/rss.xml", timeout=1.0)
    with patch("app.adapters.gdacs.httpx.AsyncClient") as mock_cls:
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("timed out"))
        mock_cls.return_value = mock_client
        with pytest.raises(AdapterError) as exc_info:
            await adapter.fetch()
    assert "timed out" in str(exc_info.value).lower() or "timeout" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_gdacs_adapter_network_error():
    """Network error → AdapterError, not a crash."""
    import httpx
    from app.adapters.gdacs import GDACSAdapter
    from app.adapters.base import AdapterError
    adapter = GDACSAdapter(feed_url="http://fake.gdacs.example/rss.xml", timeout=1.0)
    with patch("app.adapters.gdacs.httpx.AsyncClient") as mock_cls:
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("refused"))
        mock_cls.return_value = mock_client
        with pytest.raises(AdapterError):
            await adapter.fetch()


@pytest.mark.asyncio
async def test_gdacs_adapter_non_200_response():
    import httpx
    from app.adapters.gdacs import GDACSAdapter
    from app.adapters.base import AdapterError
    adapter = GDACSAdapter(feed_url="http://fake.gdacs.example/rss.xml", timeout=1.0)
    with patch("app.adapters.gdacs.httpx.AsyncClient") as mock_cls:
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=httpx.Response(503))
        mock_cls.return_value = mock_client
        with pytest.raises(AdapterError):
            await adapter.fetch()


@pytest.mark.asyncio
async def test_gdacs_adapter_max_alerts():
    """max_alerts limits the number of returned alerts."""
    import httpx as _httpx
    from app.adapters.gdacs import GDACSAdapter
    adapter = GDACSAdapter(feed_url="http://fake.gdacs.example/rss.xml", timeout=5.0, max_alerts=1)
    with patch("app.adapters.gdacs.httpx.AsyncClient") as mock_cls:
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=_httpx.Response(200, text=MINIMAL_GDACS_RSS))
        mock_cls.return_value = mock_client
        alerts = await adapter.fetch()
    assert len(alerts) <= 1


# ─── CAP adapter ──────────────────────────────────────────────────────────────

def test_cap_parse_valid():
    from app.adapters.cap import parse_cap_xml
    from app.models.alert import AlertSeverity
    alerts = parse_cap_xml(MINIMAL_CAP_XML)
    assert len(alerts) == 1
    a = alerts[0]
    assert a.source == "CAP"
    assert a.external_id == "CAP-TEST-CAP-001"
    assert a.disaster_type == "EARTHQUAKE"
    assert a.severity == AlertSeverity.HIGH
    assert a.location_name == "Test Region"
    assert a.latitude == pytest.approx(35.6762)
    assert a.longitude == pytest.approx(139.6503)
    assert a.source_url == "https://example.gov/alert/001"


def test_cap_parse_non_actual_skipped():
    from app.adapters.cap import parse_cap_xml
    alerts = parse_cap_xml(CAP_NON_ACTUAL)
    assert alerts == []


def test_cap_parse_malformed_xml():
    from app.adapters.cap import parse_cap_xml
    from app.adapters.base import AdapterError
    with pytest.raises(AdapterError):
        parse_cap_xml(MALFORMED_XML)


def test_cap_parse_missing_area():
    """CAP alert without <area> block should still parse."""
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<alert xmlns="urn:oasis:names:tc:emergency:cap:1.2">
  <identifier>TEST-CAP-003</identifier>
  <sender>test@example.gov</sender>
  <sent>2024-01-01T10:00:00</sent>
  <status>Actual</status>
  <msgType>Alert</msgType>
  <scope>Public</scope>
  <info>
    <category>Met</category>
    <event>Severe Storm</event>
    <urgency>Expected</urgency>
    <severity>Severe</severity>
    <certainty>Likely</certainty>
    <headline>Severe storm warning</headline>
  </info>
</alert>"""
    from app.adapters.cap import parse_cap_xml
    alerts = parse_cap_xml(xml)
    assert len(alerts) == 1
    assert alerts[0].location_name is None
    assert alerts[0].latitude is None


@pytest.mark.asyncio
async def test_cap_adapter_fetch():
    from app.adapters.cap import CAPAdapter
    adapter = CAPAdapter(MINIMAL_CAP_XML)
    alerts = await adapter.fetch()
    assert len(alerts) == 1
    assert alerts[0].source == "CAP"


# ─── Demo adapter ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_demo_adapter_returns_alerts():
    from app.adapters.demo import DemoAdapter
    adapter = DemoAdapter()
    alerts = await adapter.fetch()
    assert len(alerts) > 0
    for a in alerts:
        assert a.source == "DEMO"
        assert "[DEMO]" in a.title


@pytest.mark.asyncio
async def test_demo_adapter_source_name():
    from app.adapters.demo import DemoAdapter
    assert DemoAdapter().source_name == "DEMO"


# ─── Deduplication ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_upsert_creates_new_alert():
    from app.repositories.alert_repo import upsert_alert
    mock_db = MagicMock()
    mock_db.alerts.find_one = AsyncMock(return_value=None)
    inserted_doc = {
        "_id": "507f1f77bcf86cd799439011",
        "source": "GDACS", "external_id": "GDACS-EQ-001",
        "title": "Test", "disaster_type": "EARTHQUAKE",
        "status": "NEW", "severity": "MEDIUM",
        "created_at": datetime.utcnow(), "updated_at": datetime.utcnow(),
    }
    mock_db.alerts.insert_one = AsyncMock(return_value=MagicMock(inserted_id="507f1f77bcf86cd799439011"))
    mock_db.alerts.find_one = AsyncMock(side_effect=[None, inserted_doc])
    data = {"source": "GDACS", "external_id": "GDACS-EQ-001", "title": "Test", "disaster_type": "EARTHQUAKE"}
    doc, created = await upsert_alert(mock_db, data)
    assert created is True


@pytest.mark.asyncio
async def test_upsert_updates_existing_alert():
    from app.repositories.alert_repo import upsert_alert
    existing = {
        "_id": "507f1f77bcf86cd799439011",
        "source": "GDACS", "external_id": "GDACS-EQ-001",
        "title": "Old Title", "disaster_type": "EARTHQUAKE",
        "status": "NEW", "severity": "MEDIUM",
        "created_at": datetime.utcnow(), "updated_at": datetime.utcnow(),
    }
    updated = {**existing, "title": "New Title"}
    mock_db = MagicMock()
    mock_db.alerts.find_one = AsyncMock(side_effect=[existing, updated])
    mock_db.alerts.update_one = AsyncMock()
    data = {"source": "GDACS", "external_id": "GDACS-EQ-001", "title": "New Title", "disaster_type": "EARTHQUAKE"}
    doc, created = await upsert_alert(mock_db, data)
    assert created is False
    mock_db.alerts.update_one.assert_called_once()


@pytest.mark.asyncio
async def test_upsert_no_dedup_without_external_id():
    """Alerts without external_id are always inserted (DEMO alerts)."""
    from app.repositories.alert_repo import upsert_alert
    inserted_doc = {
        "_id": "507f1f77bcf86cd799439012",
        "source": "DEMO", "title": "Demo",
        "disaster_type": "FLOOD", "status": "NEW", "severity": "MEDIUM",
        "created_at": datetime.utcnow(), "updated_at": datetime.utcnow(),
    }
    mock_db = MagicMock()
    mock_db.alerts.find_one = AsyncMock(return_value=inserted_doc)
    mock_db.alerts.insert_one = AsyncMock(return_value=MagicMock(inserted_id="507f1f77bcf86cd799439012"))
    data = {"source": "DEMO", "title": "Demo", "disaster_type": "FLOOD"}  # no external_id
    doc, created = await upsert_alert(mock_db, data)
    assert created is True


@pytest.mark.asyncio
async def test_create_alert_defaults_status():
    from app.repositories.alert_repo import create_alert

    mock_db = MagicMock()
    inserted_doc = {
        "_id": "507f1f77bcf86cd799439013",
        "source": "DEMO", "title": "Demo", "disaster_type": "FLOOD",
        "severity": "MEDIUM", "status": "NEW",
        "created_at": datetime.utcnow(), "updated_at": datetime.utcnow(),
    }
    mock_db.alerts.insert_one = AsyncMock(return_value=MagicMock(inserted_id=inserted_doc["_id"]))
    mock_db.alerts.find_one = AsyncMock(return_value=inserted_doc)

    result = await create_alert(mock_db, {
        "source": "DEMO", "title": "Demo", "disaster_type": "FLOOD",
    })

    assert result["status"] == "NEW"
    assert mock_db.alerts.insert_one.call_args.args[0]["status"] == "NEW"


# ─── API endpoints ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_health_endpoint():
    mock_db = MagicMock()
    mock_db.command = AsyncMock(return_value={"ok": 1})
    with patch("main.get_db", return_value=mock_db):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get("/health")
    assert resp.status_code == 200
    assert resp.json()["service"] == "alert-service"
    assert resp.json()["version"] == "0.4.0"


@pytest.mark.asyncio
async def test_list_alerts_empty():
    with patch("app.routers.alerts.list_alerts", new_callable=AsyncMock, return_value=[]):
        with patch("app.routers.alerts.count_alerts", new_callable=AsyncMock, return_value=0):
            with patch("app.routers.alerts.get_db"):
                async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                    resp = await ac.get("/api/alerts")
    assert resp.status_code == 200
    assert resp.json()["items"] == []
    assert resp.json()["total"] == 0


@pytest.mark.asyncio
async def test_get_alert_not_found():
    with patch("app.routers.alerts.get_alert", new_callable=AsyncMock, return_value=None):
        with patch("app.routers.alerts.get_db"):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.get("/api/alerts/nonexistent")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_demo_alert_sets_source():
    created_doc = {
        "id": "507f1f77bcf86cd799439011",
        "source": "DEMO",
        "external_id": None,
        "title": "Test Alert",
        "description": None,
        "disaster_type": "FLOOD",
        "severity": "MEDIUM",
        "location_name": None,
        "latitude": None,
        "longitude": None,
        "affected_area": None,
        "issued_at": datetime.utcnow(),
        "expires_at": None,
        "source_url": None,
        "status": "NEW",
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }
    with patch("app.routers.alerts.create_alert", new_callable=AsyncMock, return_value=created_doc):
        with patch("app.routers.alerts.get_db"):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.post("/api/alerts/demo", json={
                    "title": "Test Alert",
                    "disaster_type": "FLOOD",
                })
    assert resp.status_code == 201
    assert resp.json()["source"] == "DEMO"


@pytest.mark.asyncio
async def test_fetch_alerts_adapter_error_returns_503():
    """When adapter raises AdapterError, the API returns 503."""
    from app.adapters.base import AdapterError
    with patch("app.routers.alerts.ingest_alerts", new_callable=AsyncMock,
               side_effect=AdapterError("GDACS", "Connection refused")):
        with patch("app.routers.alerts.get_db"):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.post("/api/alerts/fetch")
    assert resp.status_code == 503
    assert "unavailable" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_fetch_alerts_success():
    from app.models.alert import FetchResult
    mock_result = FetchResult(source="GDACS", fetched=5, created=4, updated=1, failed=0)
    with patch("app.routers.alerts.ingest_alerts", new_callable=AsyncMock, return_value=mock_result):
        with patch("app.routers.alerts.get_db"):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.post("/api/alerts/fetch")
    assert resp.status_code == 200
    data = resp.json()
    assert data["source"] == "GDACS"
    assert data["fetched"] == 5
    assert data["created"] == 4
    assert data["updated"] == 1
    assert data["failed"] == 0


@pytest.mark.asyncio
async def test_fetch_alerts_demo_source():
    from app.models.alert import FetchResult
    mock_result = FetchResult(source="DEMO", fetched=3, created=3, updated=0, failed=0)
    with patch("app.routers.alerts.ingest_alerts", new_callable=AsyncMock, return_value=mock_result):
        with patch("app.routers.alerts.get_db"):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.post("/api/alerts/fetch?source=DEMO")
    assert resp.status_code == 200
    assert resp.json()["source"] == "DEMO"


@pytest.mark.asyncio
async def test_invalid_alert_payload_returns_422():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/api/alerts/demo", json={"disaster_type": "FLOOD"})  # missing title
    assert resp.status_code == 422


# ─── Ingestion service ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_ingestion_calls_upsert_for_each_alert():
    from app.services.ingestion import ingest_alerts
    from app.models.alert import NormalizedAlert

    mock_alerts = [
        NormalizedAlert(external_id="X-001", source="DEMO", title="Alert 1", disaster_type="FLOOD"),
        NormalizedAlert(external_id="X-002", source="DEMO", title="Alert 2", disaster_type="FIRE"),
    ]

    mock_db = MagicMock()

    with patch("app.services.ingestion.get_adapter") as mock_get_adapter:
        mock_adapter = MagicMock()
        mock_adapter.source_name = "DEMO"
        mock_adapter.fetch = AsyncMock(return_value=mock_alerts)
        mock_get_adapter.return_value = mock_adapter

        with patch("app.services.ingestion.upsert_alert", new_callable=AsyncMock,
                   return_value=({"id": "x"}, True)) as mock_upsert:
            result = await ingest_alerts(mock_db, source="DEMO")

    assert mock_upsert.call_count == 2
    assert result.fetched == 2
    assert result.created == 2
    assert result.failed == 0
