import os
from dotenv import load_dotenv

load_dotenv()

MONGODB_URI = os.getenv("MONGO_URI", "mongodb://mongo:27017/resilientresponse")
MONGODB_DB = os.getenv("MONGODB_DB", "resilientresponse")
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")

# Service Registry self-registration
SERVICE_NAME = os.getenv("SERVICE_NAME", "alert-service")
SERVICE_INSTANCE_ID = os.getenv("SERVICE_INSTANCE_ID", "alert-primary")
SERVICE_VERSION = os.getenv("SERVICE_VERSION", "0.4.0")
SERVICE_ROLE = os.getenv("SERVICE_ROLE", "PRIMARY")
SERVICE_BASE_URL = os.getenv("SERVICE_BASE_URL", "")
SERVICE_REGISTRY_URL = os.getenv("SERVICE_REGISTRY_URL", "http://service-registry:8008")

# External alert sources
# GDACS RSS feed — publicly available, no API key required
GDACS_FEED_URL = os.getenv("GDACS_FEED_URL", "https://www.gdacs.org/xml/rss.xml")
GDACS_TIMEOUT_SECONDS = float(os.getenv("GDACS_TIMEOUT_SECONDS", "10"))
GDACS_MAX_ALERTS = int(os.getenv("GDACS_MAX_ALERTS", "0"))
GDACS_COUNTRY = os.getenv("GDACS_COUNTRY", "").strip()
GDACS_TODAY_ONLY = os.getenv("GDACS_TODAY_ONLY", "true").lower() == "true"
GDACS_REVERSE_GEOCODE = os.getenv("GDACS_REVERSE_GEOCODE", "true").lower() == "true"
GDACS_GEOCODER_URL = os.getenv("GDACS_GEOCODER_URL", "https://nominatim.openstreetmap.org/reverse")
GDACS_GEOCODER_TIMEOUT_SECONDS = float(os.getenv("GDACS_GEOCODER_TIMEOUT_SECONDS", "5"))
ALERT_TODAY_ONLY = os.getenv("ALERT_TODAY_ONLY", "true").lower() == "true"

# Active alert source: GDACS | DEMO
ALERT_SOURCE = os.getenv("ALERT_SOURCE", "GDACS")
