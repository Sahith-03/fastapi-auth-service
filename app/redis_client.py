import redis
from app.config import settings

# Create Redis client (adjust host/port/db as needed)
redis_client = redis.Redis(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    db=0,
    decode_responses=True
)
