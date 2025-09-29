# app/core/security.py
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from jose import jwt, JWTError
from passlib.context import CryptContext
from app.config import settings
import uuid
import time

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire, "scope": "access", "jti": str(uuid.uuid4())})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
def create_refresh_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS))
    to_encode.update({"exp": expire, "scope": "refresh", "jti": str(uuid.uuid4())})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        return None
        
def get_current_timestamp() -> int:
    """Return current timestamp in seconds (UTC)."""
    return int(time.time())

RESET_TOKEN_EXPIRE_SECONDS = 3600  # 1 hour

async def create_reset_token(user_id: int) -> str:
    token = str(uuid.uuid4())
    await redis_client.setex(f"reset:{token}", RESET_TOKEN_EXPIRE_SECONDS, user_id)
    return token

async def verify_reset_token(token: str) -> int | None:
    user_id = await redis_client.get(f"reset:{token}")
    if user_id:
        return int(user_id)
    return None

async def delete_reset_token(token: str):
    await redis_client.delete(f"reset:{token}")