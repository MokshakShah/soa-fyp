import os
from dotenv import load_dotenv

load_dotenv()

MONGODB_URI = os.getenv("MONGO_URI", "mongodb://mongo:27017/resilientresponse")
MONGODB_DB = os.getenv("MONGODB_DB", "resilientresponse")
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")

# Health monitoring configuration
HEALTH_CHECK_INTERVAL_SECONDS = int(os.getenv("HEALTH_CHECK_INTERVAL_SECONDS", "15"))
HEALTH_CHECK_TIMEOUT_SECONDS = float(os.getenv("HEALTH_CHECK_TIMEOUT_SECONDS", "5"))

# Health state thresholds
# Number of consecutive failures before marking DOWN
FAILURE_THRESHOLD = int(os.getenv("FAILURE_THRESHOLD", "2"))
# Number of consecutive successes before moving from RECOVERING → UP
RECOVERY_THRESHOLD = int(os.getenv("RECOVERY_THRESHOLD", "3"))
# Response time (ms) above which a service is considered DEGRADED
DEGRADED_RESPONSE_MS = int(os.getenv("DEGRADED_RESPONSE_MS", "2000"))
