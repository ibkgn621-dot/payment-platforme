from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql://payment_user:payment_pass@localhost:5432/fraud_db"
    REDIS_URL: str = "redis://:redis_pass@localhost:6379/3"
    RABBITMQ_URL: str = "amqp://rabbit_user:rabbit_pass@localhost:5672/"
    AUTH_SERVICE_URL: str = "http://localhost:8001"
    SERVICE_PORT: int = 8004
    FRAUD_SCORE_THRESHOLD: int = 70       # Score >= 70 = suspect
    MAX_TRANSACTIONS_PER_HOUR: int = 10   # Max transactions par heure
    MAX_AMOUNT_PER_DAY: float = 5_000_000 # Limite journalière GNF

    class Config:
        env_file = ".env"

settings = Settings()
