"""
Demo adapter — returns pre-defined test alerts for development.

DEMO alerts are clearly marked with source="DEMO" and must NEVER be
presented as real government or external alerts.
"""
from datetime import datetime, timedelta
from typing import List

from app.adapters.base import AlertSourceAdapter
from app.models.alert import NormalizedAlert, AlertSeverity, AlertStatus

# Fixed demo alerts — deterministic for testing
DEMO_ALERTS = [
    {
        "external_id": "DEMO-001",
        "title": "[DEMO] Flood Warning - New Delhi",
        "description": "Development test alert. Not a real emergency.",
        "disaster_type": "FLOOD",
        "severity": AlertSeverity.HIGH,
        "city": "New Delhi",
        "location_name": "Yamuna Floodplain",
        "latitude": 28.6139,
        "longitude": 77.2090,
        "affected_area": "Yamuna Floodplain",
    },
    {
        "external_id": "DEMO-002",
        "title": "[DEMO] Earthquake Alert - Mumbai",
        "description": "Development test alert. Not a real emergency.",
        "disaster_type": "EARTHQUAKE",
        "severity": AlertSeverity.CRITICAL,
        "city": "Mumbai",
        "location_name": "Mumbai Metropolitan Region",
        "latitude": 19.0760,
        "longitude": 72.8777,
        "affected_area": "Mumbai Andheri Region",
    },
    {
        "external_id": "DEMO-003",
        "title": "[DEMO] Cyclone Watch - Odisha Coast",
        "description": "Development test alert. Not a real emergency.",
        "disaster_type": "CYCLONE",
        "severity": AlertSeverity.MEDIUM,
        "location_name": "Odisha Coast",
        "latitude": 20.2961,
        "longitude": 85.8245,
        "affected_area": "Bay of Bengal Coast",
        "city": "Bhubaneswar",
    },
    {
        "external_id": "DEMO-004", "title": "[DEMO] Cyclone Watch - Chennai Coast",
        "description": "Development test alert. Not a real emergency.", "disaster_type": "CYCLONE",
        "severity": AlertSeverity.HIGH, "city": "Chennai", "location_name": "Marina Beach",
        "latitude": 13.0827, "longitude": 80.2707, "affected_area": "Chennai Coast",
    },
    {
        "external_id": "DEMO-005", "title": "[DEMO] Flood Warning - Kolkata",
        "description": "Development test alert. Not a real emergency.", "disaster_type": "FLOOD",
        "severity": AlertSeverity.MEDIUM, "city": "Kolkata", "location_name": "Hooghly River Basin",
        "latitude": 22.5726, "longitude": 88.3639, "affected_area": "Hooghly River Basin",
    },
    {
        "external_id": "DEMO-006", "title": "[DEMO] Earthquake Alert - Hyderabad",
        "description": "Development test alert. Not a real emergency.", "disaster_type": "EARTHQUAKE",
        "severity": AlertSeverity.HIGH, "city": "Hyderabad", "location_name": "HITEC City",
        "latitude": 17.3850, "longitude": 78.4867, "affected_area": "Hyderabad Metropolitan Area",
    },
    {
        "external_id": "DEMO-007", "title": "[DEMO] Wildfire Alert - Pune",
        "description": "Development test alert. Not a real emergency.", "disaster_type": "FIRE",
        "severity": AlertSeverity.MEDIUM, "city": "Pune", "location_name": "Sinhagad Hills",
        "latitude": 18.5204, "longitude": 73.8567, "affected_area": "Sinhagad Hills",
    },
    {
        "external_id": "DEMO-008", "title": "[DEMO] Heatwave Warning - Ahmedabad",
        "description": "Development test alert. Not a real emergency.", "disaster_type": "DROUGHT",
        "severity": AlertSeverity.MEDIUM, "city": "Ahmedabad", "location_name": "Sabarmati Riverfront",
        "latitude": 23.0225, "longitude": 72.5714, "affected_area": "Ahmedabad Urban Area",
    },
    {
        "external_id": "DEMO-009", "title": "[DEMO] Storm Warning - Jaipur",
        "description": "Development test alert. Not a real emergency.", "disaster_type": "STORM",
        "severity": AlertSeverity.HIGH, "city": "Jaipur", "location_name": "Jaipur District",
        "latitude": 26.9124, "longitude": 75.7873, "affected_area": "Jaipur District",
    },
    {
        "external_id": "DEMO-010", "title": "[DEMO] Landslide Watch - Lucknow",
        "description": "Development test alert. Not a real emergency.", "disaster_type": "LANDSLIDE",
        "severity": AlertSeverity.LOW, "city": "Lucknow", "location_name": "Gomti River Corridor",
        "latitude": 26.8467, "longitude": 80.9462, "affected_area": "Gomti River Corridor",
    },
    {
        "external_id": "DEMO-011", "title": "[DEMO] Flood Warning - Guwahati",
        "description": "Development test alert. Not a real emergency.", "disaster_type": "FLOOD",
        "severity": AlertSeverity.CRITICAL, "city": "Guwahati", "location_name": "Brahmaputra Riverfront",
        "latitude": 26.1445, "longitude": 91.7362, "affected_area": "Brahmaputra Riverfront",
    },
    {
        "external_id": "DEMO-012", "title": "[DEMO] Coastal Flood Alert - Kochi",
        "description": "Development test alert. Not a real emergency.", "disaster_type": "FLOOD",
        "severity": AlertSeverity.HIGH, "city": "Kochi", "location_name": "Vembanad Lake",
        "latitude": 9.9312, "longitude": 76.2673, "affected_area": "Vembanad Lake Coast",
    },
    {
        "external_id": "DEMO-013", "title": "[DEMO] Snowstorm Warning - Srinagar",
        "description": "Development test alert. Not a real emergency.", "disaster_type": "STORM",
        "severity": AlertSeverity.HIGH, "city": "Srinagar", "location_name": "Dal Lake Basin",
        "latitude": 34.0837, "longitude": 74.7973, "affected_area": "Dal Lake Basin",
    },
    {
        "external_id": "DEMO-014",
        "title": "[DEMO] Urban Flood Alert - Bengaluru",
        "description": "Development test alert. Not a real emergency.",
        "disaster_type": "FLOOD",
        "severity": AlertSeverity.HIGH,
        "city": "Bengaluru",
        "location_name": "Bellandur Lake",
        "latitude": 12.9352,
        "longitude": 77.6744,
        "affected_area": "Bellandur & Outer Ring Road",
    },
    {
        "external_id": "DEMO-015",
        "title": "[DEMO] Severe Storm Warning - Chandigarh",
        "description": "Development test alert. Not a real emergency.",
        "disaster_type": "STORM",
        "severity": AlertSeverity.MEDIUM,
        "city": "Chandigarh",
        "location_name": "Sector 17 Plaza",
        "latitude": 30.7333,
        "longitude": 76.7794,
        "affected_area": "Chandigarh Urban Sector",
    },
    {
        "external_id": "DEMO-016",
        "title": "[DEMO] Wildfire Alert - Nagpur",
        "description": "Development test alert. Not a real emergency.",
        "disaster_type": "FIRE",
        "severity": AlertSeverity.HIGH,
        "city": "Nagpur",
        "location_name": "Ambazari Lake Reserve",
        "latitude": 21.1280,
        "longitude": 79.0470,
        "affected_area": "Ambazari Lake Periphery",
    },
    {
        "external_id": "DEMO-017",
        "title": "[DEMO] Cyclone Watch - Visakhapatnam",
        "description": "Development test alert. Not a real emergency.",
        "disaster_type": "CYCLONE",
        "severity": AlertSeverity.CRITICAL,
        "city": "Visakhapatnam",
        "location_name": "RK Beach",
        "latitude": 17.6868,
        "longitude": 83.2185,
        "affected_area": "Visakhapatnam Coastline",
    },
    {
        "external_id": "DEMO-018",
        "title": "[DEMO] Coastal Flood Alert - Thiruvananthapuram",
        "description": "Development test alert. Not a real emergency.",
        "disaster_type": "FLOOD",
        "severity": AlertSeverity.MEDIUM,
        "city": "Thiruvananthapuram",
        "location_name": "Kovalam Coast",
        "latitude": 8.4004,
        "longitude": 76.9789,
        "affected_area": "Kovalam & Shanghumugham Coast",
    },
    {
        "external_id": "DEMO-019",
        "title": "[DEMO] Earthquake Alert - Bhopal",
        "description": "Development test alert. Not a real emergency.",
        "disaster_type": "EARTHQUAKE",
        "severity": AlertSeverity.HIGH,
        "city": "Bhopal",
        "location_name": "Upper Lake",
        "latitude": 23.2599,
        "longitude": 77.4126,
        "affected_area": "Bhopal Metropolitan Area",
    },
    {
        "external_id": "DEMO-020",
        "title": "[DEMO] Landslide Warning - Dehradun",
        "description": "Development test alert. Not a real emergency.",
        "disaster_type": "LANDSLIDE",
        "severity": AlertSeverity.HIGH,
        "city": "Dehradun",
        "location_name": "Mussoorie Road Hills",
        "latitude": 30.3165,
        "longitude": 78.0322,
        "affected_area": "Mussoorie Road Corridor",
    },
    {
        "external_id": "DEMO-021",
        "title": "[DEMO] River Flood Warning - Patna",
        "description": "Development test alert. Not a real emergency.",
        "disaster_type": "FLOOD",
        "severity": AlertSeverity.CRITICAL,
        "city": "Patna",
        "location_name": "Ganga Riverfront",
        "latitude": 25.5941,
        "longitude": 85.1376,
        "affected_area": "Ganga River Basin",
    },
    {
        "external_id": "DEMO-022",
        "title": "[DEMO] Storm Surge Alert - Indore",
        "description": "Development test alert. Not a real emergency.",
        "disaster_type": "STORM",
        "severity": AlertSeverity.MEDIUM,
        "city": "Indore",
        "location_name": "Rajwada Square",
        "latitude": 22.7196,
        "longitude": 75.8577,
        "affected_area": "Indore City Center",
    },
    {
        "external_id": "DEMO-023",
        "title": "[DEMO] Seismic Activity Alert - Amritsar",
        "description": "Development test alert. Not a real emergency.",
        "disaster_type": "EARTHQUAKE",
        "severity": AlertSeverity.MEDIUM,
        "city": "Amritsar",
        "location_name": "Golden Temple Area",
        "latitude": 31.6340,
        "longitude": 74.8723,
        "affected_area": "Amritsar Urban Zone",
    },
]


class DemoAdapter(AlertSourceAdapter):
    """
    Returns a fixed set of demo alerts for development and testing.
    All alerts have source='DEMO' so they are clearly distinguishable
    from real external alerts.
    """

    @property
    def source_name(self) -> str:
        return "DEMO"

    async def fetch(self) -> List[NormalizedAlert]:
        now = datetime.utcnow()
        alerts = []
        for item in DEMO_ALERTS:
            alert = NormalizedAlert(
                external_id=item["external_id"],
                source="DEMO",
                title=item["title"],
                description=item["description"],
                disaster_type=item["disaster_type"],
                severity=item["severity"],
                city=item.get("city"),
                location_name=item["location_name"],
                latitude=item["latitude"],
                longitude=item["longitude"],
                affected_area=item.get("affected_area"),
                issued_at=now,
                expires_at=now + timedelta(hours=6),
                source_url=None,
                status=AlertStatus.NEW,
                raw_data={"demo": True},
            )
            alerts.append(alert)
        return alerts
