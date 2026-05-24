from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncio
import json
import logging
from .database import engine, Base
from .routes import fraud
from .rabbitmq import start_consumer
from .detector import detector

logger = logging.getLogger(__name__)

async def handle_payment_event(message: dict):
    """Analyse automatiquement les paiements entrants"""
    data = message.get("data", {})
    event_type = message.get("event_type")
    if event_type == "created":
        score, triggered = detector.analyze(data)
        logger.info(
            f"Analyse fraude [{data.get('reference')}]: "
            f"score={score}, règles={triggered}"
        )

@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    asyncio.create_task(start_consumer(handle_payment_event))
    yield

app = FastAPI(
    title="Fraud Detection Service",
    description="Service de détection de fraude en temps réel",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(fraud.router)

@app.get("/health")
def health():
    return {"status": "healthy", "service": "fraud-service", "version": "1.0.0"}
