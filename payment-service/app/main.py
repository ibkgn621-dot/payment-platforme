import logging
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from .database import engine, Base
from .routes import payments
from .routes.payments import reconcile_stuck_transactions

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FIX 3 : Rate limiter global
limiter = Limiter(key_func=get_remote_address)

scheduler = AsyncIOScheduler()

@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    # FIX 5 : lancer le job de réconciliation toutes les 5 minutes
    scheduler.add_job(reconcile_stuck_transactions, "interval", minutes=5, id="reconcile")
    scheduler.start()
    logger.info("Scheduler de réconciliation démarré (toutes les 5 min)")
    yield
    scheduler.shutdown(wait=False)

app = FastAPI(
    title="Payment Service",
    description="Service de traitement des paiements Mobile Money",
    version="1.0.0",
    lifespan=lifespan,
)

# Rate limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(payments.router)

@app.get("/health")
def health():
    return {"status": "healthy", "service": "payment-service", "version": "1.0.0"}
