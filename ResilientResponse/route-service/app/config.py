import os
from dotenv import load_dotenv

load_dotenv()

MONGODB_URI = os.getenv("MONGO_URI", "mongodb://mongo:27017/resilientresponse")
MONGODB_DB = os.getenv("MONGODB_DB", "resilientresponse")
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")

SERVICE_NAME = os.getenv("SERVICE_NAME", "route-service")
SERVICE_INSTANCE_ID = os.getenv("SERVICE_INSTANCE_ID", "route-primary")
SERVICE_VERSION = os.getenv("SERVICE_VERSION", "0.8.0")
SERVICE_ROLE = os.getenv("SERVICE_ROLE", "PRIMARY")
SERVICE_BASE_URL = os.getenv("SERVICE_BASE_URL", "")
SERVICE_REGISTRY_URL = os.getenv("SERVICE_REGISTRY_URL", "http://service-registry:8008")

ROUTING_PROVIDER_NAME = os.getenv("ROUTING_PROVIDER", "osrm")
ROUTING_PROVIDER_URL = os.getenv(
    "ROUTING_PROVIDER_URL",
    "https://router.project-osrm.org",
)
ROUTING_REQUEST_TIMEOUT = float(os.getenv("ROUTING_REQUEST_TIMEOUT", "15.0"))
