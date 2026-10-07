import os
from dotenv import load_dotenv

load_dotenv()

MONGODB_URI = os.getenv("MONGO_URI", "mongodb://mongo:27017/resilientresponse")
MONGODB_DB = os.getenv("MONGODB_DB", "resilientresponse")
CORS_ORIGINS = ["*"]

# Self-registration
SERVICE_NAME = os.getenv("SERVICE_NAME", "notification-service")
SERVICE_INSTANCE_ID = os.getenv("SERVICE_INSTANCE_ID", "notification-primary")
SERVICE_VERSION = os.getenv("SERVICE_VERSION", "0.9.0")
SERVICE_ROLE = os.getenv("SERVICE_ROLE", "PRIMARY")
SERVICE_BASE_URL = os.getenv("SERVICE_BASE_URL", "")
SERVICE_REGISTRY_URL = os.getenv("SERVICE_REGISTRY_URL", "http://service-registry:8008")

# Provider — only DEMO (log provider) in Phase 9.
# Set NOTIFICATION_PROVIDER=SMS when a real provider is added.
NOTIFICATION_PROVIDER = os.getenv("NOTIFICATION_PROVIDER", "DEMO")
