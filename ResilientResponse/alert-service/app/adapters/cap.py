"""
CAP (Common Alerting Protocol) adapter.

CAP is an international standard (OASIS CAP 1.2) used by many national
emergency alert systems including NDMA SACHET (India).

This adapter parses a standard CAP XML document and converts it to the
internal NormalizedAlert format. It does NOT hardcode any single government's
payload — it is reusable for any CAP-compliant source.

CAP 1.2 namespace: urn:oasis:names:tc:emergency:cap:1.2
"""
import logging
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import List, Optional, Dict, Any

from app.adapters.base import AlertSourceAdapter, AdapterError
from app.models.alert import NormalizedAlert, AlertSeverity, AlertStatus

logger = logging.getLogger("adapter.cap")

CAP_NS = "urn:oasis:names:tc:emergency:cap:1.2"
CAP_TAG = f"{{{CAP_NS}}}"

# CAP severity → internal severity
CAP_SEVERITY_MAP = {
    "Extreme":  AlertSeverity.CRITICAL,
    "Severe":   AlertSeverity.HIGH,
    "Moderate": AlertSeverity.MEDIUM,
    "Minor":    AlertSeverity.LOW,
    "Unknown":  AlertSeverity.MEDIUM,
}

# CAP event category → disaster_type (best-effort mapping)
CAP_CATEGORY_MAP = {
    "Geo":    "EARTHQUAKE",
    "Met":    "CYCLONE",
    "Fire":   "FIRE",
    "Flood":  "FLOOD",
    "CBRNE":  "HAZMAT",
    "Safety": "SAFETY",
    "Other":  "OTHER",
}


def _tag(name: str) -> str:
    return f"{CAP_TAG}{name}"


def _text(el: Optional[ET.Element]) -> Optional[str]:
    if el is None:
        return None
    return (el.text or "").strip() or None


def _parse_cap_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    # CAP uses ISO 8601 with optional timezone offset
    try:
        cleaned = value.strip()
        # Remove timezone info for naive datetime storage
        if cleaned.endswith("Z"):
            cleaned = cleaned[:-1]
        elif "+" in cleaned[10:]:
            cleaned = cleaned[: cleaned.rfind("+")]
        elif cleaned.count("-") > 2:
            # Has negative offset like 2024-01-01T12:00:00-05:00
            idx = cleaned.rfind("-")
            if idx > 10:
                cleaned = cleaned[:idx]
        return datetime.fromisoformat(cleaned)
    except Exception:
        return None


def _map_severity(cap_severity: Optional[str]) -> AlertSeverity:
    if not cap_severity:
        return AlertSeverity.MEDIUM
    return CAP_SEVERITY_MAP.get(cap_severity.strip(), AlertSeverity.MEDIUM)


def _map_disaster_type(cap_event: Optional[str], cap_category: Optional[str]) -> str:
    """
    Try to determine disaster type from CAP event string or category.
    The event field is free-text so we do keyword matching.
    """
    if cap_event:
        ev = cap_event.upper()
        for keyword, dtype in [
            ("FLOOD", "FLOOD"), ("EARTHQUAKE", "EARTHQUAKE"), ("QUAKE", "EARTHQUAKE"),
            ("CYCLONE", "CYCLONE"), ("TYPHOON", "CYCLONE"), ("HURRICANE", "CYCLONE"),
            ("FIRE", "FIRE"), ("WILDFIRE", "FIRE"), ("TSUNAMI", "TSUNAMI"),
            ("LANDSLIDE", "LANDSLIDE"), ("DROUGHT", "DROUGHT"), ("VOLCANO", "VOLCANO"),
            ("STORM", "STORM"), ("HEAT", "HEATWAVE"), ("COLD", "COLDWAVE"),
        ]:
            if keyword in ev:
                return dtype
    if cap_category:
        return CAP_CATEGORY_MAP.get(cap_category.strip(), "OTHER")
    return "OTHER"


def parse_cap_xml(xml_text: str) -> List[NormalizedAlert]:
    """
    Parse a CAP 1.2 XML document and return NormalizedAlert objects.

    A single CAP document is one <alert> with one or more <info> blocks.
    We create one NormalizedAlert per document (using the first info block).
    """
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise AdapterError("CAP", f"Invalid XML: {exc}", exc)

    # Support both namespaced and non-namespaced CAP
    if root.tag == _tag("alert"):
        ns_prefix = CAP_TAG
    elif root.tag == "alert":
        ns_prefix = ""
    else:
        raise AdapterError("CAP", f"Root element is not <alert>: {root.tag}")

    def t(name: str) -> str:
        return f"{ns_prefix}{name}" if ns_prefix else name

    identifier = _text(root.find(t("identifier"))) or ""
    sender = _text(root.find(t("sender"))) or ""
    sent = _parse_cap_datetime(_text(root.find(t("sent"))))
    status_raw = _text(root.find(t("status"))) or "Actual"
    msg_type = _text(root.find(t("msgType"))) or "Alert"

    # Only process Actual alerts (skip Test, Draft, System, etc.)
    if status_raw not in ("Actual",):
        logger.info("Skipping non-Actual CAP alert: status=%s identifier=%s", status_raw, identifier)
        return []

    alerts: List[NormalizedAlert] = []

    for info in root.findall(t("info")):
        try:
            language = _text(info.find(t("language"))) or "en"
            category = _text(info.find(t("category")))
            event = _text(info.find(t("event")))
            urgency = _text(info.find(t("urgency")))
            severity_raw = _text(info.find(t("severity")))
            certainty = _text(info.find(t("certainty")))
            effective = _parse_cap_datetime(_text(info.find(t("effective"))))
            onset = _parse_cap_datetime(_text(info.find(t("onset"))))
            expires = _parse_cap_datetime(_text(info.find(t("expires"))))
            headline = _text(info.find(t("headline")))
            description = _text(info.find(t("description")))
            web = _text(info.find(t("web")))

            # Geographic area (first <area> block)
            area_el = info.find(t("area"))
            area_desc = _text(area_el.find(t("areaDesc"))) if area_el is not None else None

            # Try to extract point coordinates from <circle> or <polygon>
            latitude: Optional[float] = None
            longitude: Optional[float] = None
            if area_el is not None:
                circle = _text(area_el.find(t("circle")))
                if circle:
                    # Format: "lat,lon radius"
                    try:
                        point = circle.split()[0]
                        lat_s, lon_s = point.split(",")
                        latitude = float(lat_s)
                        longitude = float(lon_s)
                    except Exception:
                        pass

                if latitude is None:
                    polygon = _text(area_el.find(t("polygon")))
                    if polygon:
                        # Take centroid of first point pair as approximate location
                        try:
                            first_pair = polygon.strip().split()[0]
                            lat_s, lon_s = first_pair.split(",")
                            latitude = float(lat_s)
                            longitude = float(lon_s)
                        except Exception:
                            pass

            raw: Dict[str, Any] = {
                "identifier": identifier,
                "sender": sender,
                "status": status_raw,
                "msgType": msg_type,
                "language": language,
                "category": category,
                "urgency": urgency,
                "certainty": certainty,
            }

            external_id = f"CAP-{identifier}" if identifier else None

            alert = NormalizedAlert(
                external_id=external_id,
                source="CAP",
                title=headline or event or "CAP Alert",
                description=description,
                disaster_type=_map_disaster_type(event, category),
                severity=_map_severity(severity_raw),
                location_name=area_desc,
                latitude=latitude,
                longitude=longitude,
                affected_area=area_desc,
                issued_at=effective or onset or sent,
                expires_at=expires,
                source_url=web,
                status=AlertStatus.NEW,
                raw_data=raw,
            )
            alerts.append(alert)

        except Exception as exc:
            logger.warning("Skipping malformed CAP info block: %s", exc)
            continue

    return alerts


class CAPAdapter(AlertSourceAdapter):
    """
    CAP adapter — parses a provided CAP XML string.

    Unlike GDACS this adapter does not fetch from a URL itself;
    the caller provides the XML (e.g. received via webhook or polled endpoint).
    Use CAPAdapter.from_xml(xml_text) directly.
    """

    def __init__(self, xml_text: str):
        self._xml_text = xml_text

    @property
    def source_name(self) -> str:
        return "CAP"

    async def fetch(self) -> List[NormalizedAlert]:
        return parse_cap_xml(self._xml_text)
