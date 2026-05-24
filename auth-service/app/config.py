from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql://payment_user:payment_pass@localhost:5432/auth_db"
    REDIS_URL: str = "redis://:redis_pass@localhost:6379/0"
    SECRET_KEY: str = "change-this-super-secret-key-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    SERVICE_PORT: int = 8001

    class Config:
        env_file = ".env"

settings = Settings()
