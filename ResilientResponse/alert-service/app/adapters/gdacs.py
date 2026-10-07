"""
GDACS (Global Disaster Alert and Coordination System) adapter.

Fetches the public GDACS RSS feed — no API key required.
Feed URL: https://www.gdacs.org/xml/rss.xml

The feed uses RSS 2.0 with GDACS-specific XML namespaces.

Namespace references:
  gdacs: http://www.gdacs.org
  geo:   http://www.w3.org/2003/01/geo/wgs84_pos#
  dc:    http://purl.org/dc/elements/1.1/
"""
import logging
import re
import xml.etree.ElementTree as ET
from datetime import date, datetime, timezone
from email.utils import parsedate_to_datetime
from typing import List, Optional, Dict, Any

import httpx

from app.adapters.base import AlertSourceAdapter, AdapterError
from app.models.alert import NormalizedAlert, AlertSeverity, AlertStatus

logger = logging.getLogger("adapter.gdacs")

# XML namespaces used in the GDACS RSS feed
NS = {
    "gdacs": "http://www.gdacs.org",
    "geo":   "http://www.w3.org/2003/01/geo/wgs84_pos#",
    "georss": "http://www.georss.org/georss",
    "dc":    "http://purl.org/dc/elements/1.1/",
}

# GDACS event type codes → our disaster_type strings
GDACS_EVENT_MAP = {
    "EQ": "EARTHQUAKE",
    "TC": "CYCLONE",
    "FL": "FLOOD",
    "VO": "VOLCANO",
    "DR": "DROUGHT",
    "WF": "WILDFIRE",
    "TS": "TSUNAMI",
}

# GDACS alert level → our severity
GDACS_ALERT_MAP = {
    "Red":    AlertSeverity.CRITICAL,
    "Orange": AlertSeverity.HIGH,
    "Green":  AlertSeverity.MEDIUM,
}


def _parse_gdacs_severity(alert_level: Optional[str]) -> AlertSeverity:
    if not alert_level:
        return AlertSeverity.MEDIUM
    return GDACS_ALERT_MAP.get(alert_level.strip().capitalize(), AlertSeverity.MEDIUM)


def _parse_gdacs_disaster_type(event_type: Optional[str]) -> str:
    if not event_type:
        return "OTHER"
    return GDACS_EVENT_MAP.get(event_type.strip().upper(), event_type.strip().upper())


def _parse_date(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return parsedate_to_datetime(value.strip()).replace(tzinfo=None)
    except Exception:
        try:
            # Try ISO format as fallback
            return datetime.fromisoformat(value.strip().replace("Z", "+00:00")).replace(tzinfo=None)
        except Exception:
            return None


def _text(element: Optional[ET.Element]) -> Optional[str]:
    if element is None:
        return None
    t = element.text
    return t.strip() if t else None


def _matches_country_filter(country: Optional[str], country_filter: str) -> bool:
    """Match India regional labels such as ``Southern India``."""
    if not country:
        return False
    if country.casefold() == country_filter.casefold():
        return True
    if country_filter.casefold() == "india":
        return re.search(r"\bindia\b", country, re.IGNORECASE) is not None
    return False


async def _enrich_locations(
    alerts: List[NormalizedAlert],
    client: httpx.AsyncClient,
    geocoder_url: str,
) -> None:
    """Add city names from alert coordinates without making geocoding fatal."""
    cache: Dict[tuple[float, float], Optional[str]] = {}
    for alert in alerts:
        if alert.latitude is None or alert.longitude is None:
            continue
        key = (round(alert.latitude, 4), round(alert.longitude, 4))
        if key not in cache:
            try:
                response = await client.get(
                    geocoder_url,
                    params={
                        "format": "jsonv2",
                        "lat": alert.latitude,
                        "lon": alert.longitude,
                        "zoom": 10,
                        "addressdetails": 1,
                        "accept-language": "en",
                    },
                    headers={"User-Agent": "ResilientResponse/1.0 disaster-monitoring"},
                )
                if response.status_code == 200:
                    address = response.json().get("address", {})
                    cache[key] = (
                        address.get("city")
                        or address.get("town")
                        or address.get("municipality")
                        or address.get("village")
                    )
                else:
                    cache[key] = None
            except (httpx.HTTPError, ValueError, TypeError) as exc:
                logger.warning("Reverse geocoding failed for %s,%s: %s", alert.latitude, alert.longitude, exc)
                cache[key] = None

        city = cache[key]
        if city:
            alert.city = city
            alert.location_name = f"{city}, {alert.location_name}" if alert.location_name else city


def parse_gdacs_feed(
    xml_text: str,
    country_filter: Optional[str] = None,
    published_on: Optional[date] = None,
) -> List[NormalizedAlert]:
    """Parse GDACS RSS XML with optional country and publication-date filters."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise AdapterError("GDACS", f"Invalid XML: {exc}", exc)

    channel = root.find("channel")
    if channel is None:
        raise AdapterError("GDACS", "RSS feed has no <channel> element")

    alerts: List[NormalizedAlert] = []
    seen_event_keys: set[str] = set()

    for item in channel.findall("item"):
        try:
            title = _text(item.find("title")) or "GDACS Alert"
            description = _text(item.find("description"))
            link = _text(item.find("link"))
            pub_date = _parse_date(_text(item.find("pubDate")))

            # GDACS-specific fields
            event_type = _text(item.find("gdacs:eventtype", NS))
            alert_level = _text(item.find("gdacs:alertlevel", NS))
            event_id = _text(item.find("gdacs:eventid", NS))
            episode_id = _text(item.find("gdacs:episodeid", NS))
            country = _text(item.find("gdacs:country", NS))
            from_date = _parse_date(_text(item.find("gdacs:fromdate", NS)))
            event_date = from_date or pub_date
            if published_on and event_date and event_date.date() != published_on:
                continue
            if country_filter and not _matches_country_filter(country, country_filter):
                continue
            to_date = _parse_date(_text(item.find("gdacs:todate", NS)))
            affected_population = _text(item.find("gdacs:population", NS))

            # Geographic coordinates
            lat_text = _text(item.find("geo:lat", NS)) or _text(item.find("geo:Point/geo:lat", NS))
            lon_text = _text(item.find("geo:long", NS)) or _text(item.find("geo:Point/geo:long", NS))
            if not lat_text or not lon_text:
                point = _text(item.find("georss:point", NS))
                if point:
                    point_parts = point.split()
                    if len(point_parts) == 2:
                        lat_text, lon_text = point_parts
            latitude: Optional[float] = None
            longitude: Optional[float] = None
            try:
                if lat_text:
                    latitude = float(lat_text)
                if lon_text:
                    longitude = float(lon_text)
            except (ValueError, TypeError):
                pass

            # Use the provider event identity, not the episode or location.
            # Episodes are updates to one event and must not create new alerts.
            if event_id:
                external_id = f"GDACS-{event_type or 'EV'}-{event_id}"
            else:
                # Fall back to link as external ID
                external_id = link or title[:80]

            if external_id in seen_event_keys:
                continue
            seen_event_keys.add(external_id)

            # Raw data preserved for auditability
            raw: Dict[str, Any] = {
                "event_type": event_type,
                "alert_level": alert_level,
                "event_id": event_id,
                "episode_id": episode_id,
                "country": country,
                "affected_population": affected_population,
            }

            alert = NormalizedAlert(
                external_id=external_id,
                source="GDACS",
                title=title,
                description=description,
                disaster_type=_parse_gdacs_disaster_type(event_type),
                severity=_parse_gdacs_severity(alert_level),
                location_name=country,
                latitude=latitude,
                longitude=longitude,
                issued_at=event_date,
                expires_at=to_date,
                source_url=link,
                status=AlertStatus.NEW,
                raw_data=raw,
            )
            alerts.append(alert)

        except Exception as exc:
            # Skip malformed items — log and continue
            logger.warning("Skipping malformed GDACS item: %s", exc)
            continue

    logger.info("Parsed %d alerts from GDACS feed", len(alerts))
    return alerts


class GDACSAdapter(AlertSourceAdapter):
    """
    Fetches disaster alerts from the public GDACS RSS feed.
    No API key required.
    """

    def __init__(
        self,
        feed_url: str,
        timeout: float = 10.0,
        max_alerts: int = 0,
        country_filter: Optional[str] = None,
        today_only: bool = False,
        reverse_geocode: bool = False,
        geocoder_url: str = "https://nominatim.openstreetmap.org/reverse",
    ):
        self._feed_url = feed_url
        self._timeout = timeout
        self._max_alerts = max_alerts
        self._country_filter = country_filter
        self._today_only = today_only
        self._reverse_geocode = reverse_geocode
        self._geocoder_url = geocoder_url

    @property
    def source_name(self) -> str:
        return "GDACS"

    async def fetch(self) -> List[NormalizedAlert]:
        logger.info("Fetching GDACS feed: %s", self._feed_url)
        try:
            async with httpx.AsyncClient(timeout=self._timeout, follow_redirects=True) as client:
                resp = await client.get(
                    self._feed_url,
                    headers={"User-Agent": "ResilientResponse/0.4 (disaster-monitoring)"},
                )
            if resp.status_code != 200:
                raise AdapterError(
                    "GDACS",
                    f"Feed returned HTTP {resp.status_code}",
                )
            alerts = parse_gdacs_feed(
                resp.text,
                country_filter=self._country_filter,
                published_on=datetime.now(timezone.utc).date() if self._today_only else None,
            )
            if self._reverse_geocode:
                async with httpx.AsyncClient(timeout=self._timeout) as geocode_client:
                    await _enrich_locations(alerts, geocode_client, self._geocoder_url)
            return alerts if self._max_alerts <= 0 else alerts[: self._max_alerts]

        except AdapterError:
            raise
        except httpx.TimeoutException as exc:
            raise AdapterError("GDACS", f"Request timed out after {self._timeout}s", exc)
        except httpx.RequestError as exc:
            raise AdapterError("GDACS", f"Network error: {exc}", exc)
        except Exception as exc:
            raise AdapterError("GDACS", f"Unexpected error: {exc}", exc)
