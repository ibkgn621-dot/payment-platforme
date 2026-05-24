import logging
import asyncio
from contextlib import asynccontextmanager
from decimal import Decimal

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import engine, Base, SessionLocal
from .routes import wallets
from .rabbitmq import start_consumer
from . import models

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def handle_payment_event(message: dict):
    """
    Traite les événements de paiement reçus via RabbitMQ.
    - payment.success → crédite le wallet du marchand
    - payment.failed  → log uniquement
    """
    event_type = message.get("event_type")
    data = message.get("data", {})
    reference = data.get("reference", "N/A")

    logger.info(f"Événement reçu: {event_type} — {reference}")

    if event_type == "success":
        merchant_id = data.get("merchant_id")
        amount = data.get("amount")
        transaction_id = data.get("transaction_id")
        currency = data.get("currency", "GNF")

        if not merchant_id or not amount:
            logger.warning(f"Données incomplètes pour créditer le wallet: {data}")
            return

        db = SessionLocal()
        try:
            # Chercher ou créer le wallet du marchand
            wallet = db.query(models.Wallet).filter(
                models.Wallet.owner_id == merchant_id
            ).with_for_update().first()

            if not wallet:
                logger.info(f"Création automatique du wallet pour le marchand {merchant_id}")
                wallet = models.Wallet(
                    owner_id=merchant_id,
                    owner_type="merchant",
                    currency=currency,
                    balance=Decimal("0"),
                    available_balance=Decimal("0"),
                    frozen_balance=Decimal("0"),
                )
                db.add(wallet)
                db.flush()

            if wallet.status != models.WalletStatus.ACTIVE:
                logger.warning(f"Wallet {wallet.id} non actif, crédit ignoré")
                return

            credit_amount = Decimal(str(amount))
            balance_before = wallet.balance
            wallet.balance += credit_amount
            wallet.available_balance += credit_amount

            # Vérifier idempotence : ne pas créditer deux fois la même transaction
            existing_ledger = db.query(models.WalletLedger).filter(
                models.WalletLedger.reference == reference,
                models.WalletLedger.wallet_id == wallet.id,
            ).first()
            if existing_ledger:
                logger.info(f"Transaction {reference} déjà créditée, ignorée")
                return

            entry = models.WalletLedger(
                wallet_id=wallet.id,
                type=models.LedgerType.CREDIT,
                amount=credit_amount,
                reference=reference,
                description=f"Paiement reçu via {data.get('operator', 'opérateur')}",
                balance_before=balance_before,
                balance_after=wallet.balance,
                transaction_id=transaction_id,
            )
            db.add(entry)
            db.commit()
            logger.info(
                f"Wallet {wallet.id} crédité de {credit_amount} GNF "
                f"(nouveau solde: {wallet.balance})"
            )
        except Exception as exc:
            logger.exception(f"Erreur crédit wallet pour {reference}: {exc}")
            db.rollback()
        finally:
            db.close()

    elif event_type == "failed":
        logger.info(f"Paiement échoué ignoré: {reference} — {data.get('error')}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    asyncio.create_task(start_consumer(handle_payment_event))
    yield

app = FastAPI(
    title="Wallet Service",
    description="Service de gestion des portefeuilles électroniques",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(wallets.router)

@app.get("/health")
def health():
    return {"status": "healthy", "service": "wallet-service", "version": "1.0.0"}
