from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql://payment_user:payment_pass@localhost:5432/payment_db"
    REDIS_URL: str = "redis://:redis_pass@localhost:6379/1"
    RABBITMQ_URL: str = "amqp://rabbit_user:rabbit_pass@localhost:5672/"
    AUTH_SERVICE_URL: str = "http://localhost:8001"
    SERVICE_PORT: int = 8002
    WEBHOOK_SECRET: str = "change-this-webhook-secret"
    # Opérateurs Mobile Money
    ORANGE_MONEY_API_URL: str = "https://api.orange.com/orange-money-webpay/dev/v1"
    ORANGE_MONEY_API_KEY: str = ""
    MTN_MOMO_API_URL: str = "https://sandbox.momodeveloper.mtn.com"
    MTN_MOMO_API_KEY: str = ""
    WAVE_API_URL: str = "https://api.wave.com/v1"
    WAVE_API_KEY: str = ""

    class Config:
        env_file = ".env"

settings = Settings()
