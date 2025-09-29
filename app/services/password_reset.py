import uuid
from app.config import settings
from redis import asyncio as aioredis

async def create_reset_token(user_id: int) -> str:
    token = str(uuid.uuid4())
    redis = aioredis.Redis.from_url(settings.REDIS_URL)
    await redis.setex(f"reset:{token}", 900, user_id)  # 15 min expiry
    return token

async def verify_reset_token(token: str):
    redis = aioredis.Redis.from_url(settings.REDIS_URL)
    user_id = await redis.get(f"reset:{token}")
    if user_id:
        return int(user_id)
    return None

async def delete_reset_token(token: str):
    redis = aioredis.Redis.from_url(settings.REDIS_URL)
    await redis.delete(f"reset:{token}")
