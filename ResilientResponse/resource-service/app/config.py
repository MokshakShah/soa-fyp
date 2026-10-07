import os
from dotenv import load_dotenv

load_dotenv()

MONGODB_URI = os.getenv("MONGO_URI", "mongodb://mongo:27017/resilientresponse")
MONGODB_DB = os.getenv("MONGODB_DB", "resilientresponse")
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")

SERVICE_NAME = os.getenv("SERVICE_NAME", "resource-service")
SERVICE_INSTANCE_ID = os.getenv("SERVICE_INSTANCE_ID", "resource-primary")
SERVICE_VERSION = os.getenv("SERVICE_VERSION", "0.3.0")
SERVICE_ROLE = os.getenv("SERVICE_ROLE", "PRIMARY")
SERVICE_BASE_URL = os.getenv("SERVICE_BASE_URL", "")
SERVICE_REGISTRY_URL = os.getenv("SERVICE_REGISTRY_URL", "http://service-registry:8008")
