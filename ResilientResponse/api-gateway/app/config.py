import os
from dotenv import load_dotenv

load_dotenv()

MONGODB_URI = os.getenv("MONGO_URI", "mongodb://mongo:27017/resilientresponse")
MONGODB_DB = os.getenv("MONGODB_DB", "resilientresponse")
JWT_SECRET = os.getenv("JWT_SECRET", "change-this-in-production-supersecret")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "480"))

CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")

# Downstream service URLs used by the reverse proxy.
# The gateway uses fixed URLs for admin CRUD proxying (always hits PRIMARY).
# The Orchestrator uses the Service Registry for dynamic discovery and failover.
SERVICE_URLS = {
    "orchestrator":            os.getenv("ORCHESTRATOR_URL", "http://orchestrator:8001"),
    "alert-service":           os.getenv("ALERT_SERVICE_URL", "http://alert-service:8002"),
    "classification-service":  os.getenv("CLASSIFICATION_SERVICE_URL", "http://classification-service:8003"),
    # Gateway proxies to the PRIMARY hospital/resource instance.
    # For failover the Orchestrator uses discovery; the admin CRUD stays on PRIMARY.
    "hospital-service":        os.getenv("HOSPITAL_SERVICE_URL", "http://hospital-primary:8004"),
    "resource-service":        os.getenv("RESOURCE_SERVICE_URL", "http://resource-primary:8005"),
    "route-service":           os.getenv("ROUTE_SERVICE_URL", "http://route-service:8006"),
    "notification-service":    os.getenv("NOTIFICATION_SERVICE_URL", "http://notification-service:8007"),
    "service-registry":        os.getenv("SERVICE_REGISTRY_URL", "http://service-registry:8008"),
}
