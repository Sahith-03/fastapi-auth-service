# app/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # JWT/Auth
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Database
    DATABASE_USER: str
    DATABASE_PASSWORD: str
    DATABASE_NAME: str
    DATABASE_URL: str

    # Redis
    REDIS_HOST: str
    REDIS_PORT: int
    REDIS_URL: str

    # SendGrid
    SENDGRID_API_KEY: str = ""
    EMAIL_FROM: str = "noreply@yourapp.com"

    class Config:
        env_file = ".env.dev"
        extra = "allow"

settings = Settings()
