from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql://payment_user:payment_pass@localhost:5432/wallet_db"
    REDIS_URL: str = "redis://:redis_pass@localhost:6379/2"
    RABBITMQ_URL: str = "amqp://rabbit_user:rabbit_pass@localhost:5672/"
    AUTH_SERVICE_URL: str = "http://localhost:8001"
    SERVICE_PORT: int = 8003

    class Config:
        env_file = ".env"

settings = Settings()
