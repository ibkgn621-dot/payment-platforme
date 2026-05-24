import json
import hmac
import hashlib
import random
import string
import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import desc

from .. import models, schemas
from ..database import get_db, SessionLocal
from ..config import settings
from ..rabbitmq import publish_payment_created, publish_payment_success, publish_payment_failed
from ..connectors.orange_money import orange_money
from ..connectors.mtn_momo import mtn_momo
from ..connectors.wave import wave

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["Payments"])


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def generate_reference(prefix="TXN") -> str:
    chars = string.ascii_uppercase + string.digits
    suffix = "".join(random.choices(chars, k=10))
    return f"{prefix}-{suffix}"


def calculate_fees(amount: float, operator: models.PaymentOperator) -> float:
    """Calcule les frais selon l'opérateur."""
    fee_rates = {
        models.PaymentOperator.ORANGE_MONEY: 0.02,
        models.PaymentOperator.MTN_MOMO: 0.015,
        models.PaymentOperator.WAVE: 0.01,
        models.PaymentOperator.VISA: 0.025,
        models.PaymentOperator.MASTERCARD: 0.025,
    }
    return round(float(amount) * fee_rates.get(operator, 0.02), 2)


async def process_payment_with_operator(transaction: models.Transaction) -> dict:
    """Traite le paiement avec l'opérateur approprié."""
    amount = float(transaction.amount)
    phone = transaction.phone_number or ""
    reference = transaction.reference

    if transaction.operator == models.PaymentOperator.ORANGE_MONEY:
        return await orange_money.initiate_payment(phone, amount, reference)
    elif transaction.operator == models.PaymentOperator.MTN_MOMO:
        return await mtn_momo.request_to_pay(phone, amount, reference)
    elif transaction.operator == models.PaymentOperator.WAVE:
        return await wave.initiate_checkout(phone, amount, reference)
    return {"success": False, "error": f"Opérateur {transaction.operator} non supporté"}


# ─────────────────────────────────────────────
# FIX 1 : Background task avec sa propre session DB
# ─────────────────────────────────────────────

async def _process_operator_payment(transaction_id: str):
    """
    Traitement asynchrone avec l'opérateur.
    Crée sa propre session pour ne pas dépendre de la session HTTP (déjà fermée).
    """
    db: Session = SessionLocal()
    try:
        transaction = db.query(models.Transaction).filter(
            models.Transaction.id == transaction_id
        ).first()
        if not transaction:
            logger.warning(f"Transaction {transaction_id} introuvable pour traitement opérateur")
            return

        # Idempotence : ne pas retraiter si déjà en cours ou terminée
        if transaction.status not in (
            models.TransactionStatus.PENDING,
            models.TransactionStatus.PROCESSING,
        ):
            logger.info(f"Transaction {transaction_id} déjà traitée (status={transaction.status}), ignorée")
            return

        transaction.status = models.TransactionStatus.PROCESSING
        db.commit()

        result = await process_payment_with_operator(transaction)

        if result.get("success"):
            transaction.status = models.TransactionStatus.SUCCESS
            transaction.operator_transaction_id = result.get("operator_reference")
            transaction.completed_at = datetime.utcnow()
            db.commit()
            await publish_payment_success({
                "transaction_id": str(transaction.id),
                "reference": transaction.reference,
                "merchant_id": str(transaction.merchant_id),
                "amount": str(transaction.amount),
                "currency": transaction.currency,
            })
        else:
            transaction.status = models.TransactionStatus.FAILED
            transaction.error_message = result.get("error", "Erreur inconnue")
            db.commit()
            await publish_payment_failed({
                "transaction_id": str(transaction.id),
                "reference": transaction.reference,
                "error": transaction.error_message,
            })
    except Exception as exc:
        logger.exception(f"Erreur inattendue pour transaction {transaction_id}: {exc}")
        try:
            db.rollback()
        except Exception:
            pass
    finally:
        db.close()


# ─────────────────────────────────────────────
# FIX 5 : Job de réconciliation (transactions bloquées en PROCESSING)
# ─────────────────────────────────────────────

async def reconcile_stuck_transactions():
    """
    Relance les transactions restées en PROCESSING depuis plus de 10 minutes.
    Appelé périodiquement par APScheduler depuis main.py.
    """
    db: Session = SessionLocal()
    try:
        cutoff = datetime.utcnow() - timedelta(minutes=10)
        stuck = db.query(models.Transaction).filter(
            models.Transaction.status == models.TransactionStatus.PROCESSING,
            models.Transaction.created_at < cutoff,
        ).all()

        if stuck:
            logger.info(f"Réconciliation : {len(stuck)} transaction(s) bloquée(s) trouvée(s)")
        for txn in stuck:
            logger.info(f"Relance transaction bloquée : {txn.reference}")
            # Repasser en PENDING pour permettre le retraitement
            txn.status = models.TransactionStatus.PENDING
            db.commit()
            await _process_operator_payment(str(txn.id))
    except Exception as exc:
        logger.exception(f"Erreur réconciliation : {exc}")
    finally:
        db.close()


# ─────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────

@router.post("/payment/create", response_model=schemas.TransactionResponse, status_code=201)
async def create_payment(
    payment: schemas.PaymentCreate,
    background_tasks: BackgroundTasks,
    request: Request,
    db: Session = Depends(get_db),
):
    fees = calculate_fees(float(payment.amount), payment.operator)
    net_amount = float(payment.amount) - fees

    transaction = models.Transaction(
        reference=generate_reference(),
        merchant_id=payment.merchant_id,
        amount=payment.amount,
        currency=payment.currency,
        operator=payment.operator,
        phone_number=payment.phone_number,
        description=payment.description,
        callback_url=payment.callback_url,
        metadata=json.dumps(payment.metadata) if payment.metadata else None,
        fees=fees,
        net_amount=net_amount,
        ip_address=request.client.host if request.client else None,
    )
    db.add(transaction)
    db.commit()
    db.refresh(transaction)

    # Publier événement RabbitMQ
    background_tasks.add_task(
        publish_payment_created,
        {
            "transaction_id": str(transaction.id),
            "reference": transaction.reference,
            "merchant_id": str(transaction.merchant_id),
            "amount": str(transaction.amount),
            "currency": transaction.currency,
            "operator": transaction.operator,
            "phone_number": transaction.phone_number,
        },
    )

    # FIX 1 : passer uniquement l'ID, pas la session DB
    background_tasks.add_task(_process_operator_payment, str(transaction.id))

    return transaction


@router.post("/payment/verify", response_model=schemas.TransactionResponse)
async def verify_payment(data: schemas.PaymentVerify, db: Session = Depends(get_db)):
    transaction = db.query(models.Transaction).filter(
        models.Transaction.reference == data.reference
    ).first()
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction introuvable")
    return transaction


@router.get("/transactions", response_model=schemas.TransactionList)
def list_transactions(
    merchant_id: Optional[str] = None,
    status: Optional[models.TransactionStatus] = None,
    operator: Optional[models.PaymentOperator] = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    query = db.query(models.Transaction)
    if merchant_id:
        query = query.filter(models.Transaction.merchant_id == merchant_id)
    if status:
        query = query.filter(models.Transaction.status == status)
    if operator:
        query = query.filter(models.Transaction.operator == operator)

    total = query.count()
    items = query.order_by(desc(models.Transaction.created_at)).offset(skip).limit(limit).all()
    return schemas.TransactionList(total=total, items=items)


@router.get("/transactions/{transaction_id}", response_model=schemas.TransactionResponse)
def get_transaction(transaction_id: str, db: Session = Depends(get_db)):
    transaction = db.query(models.Transaction).filter(
        models.Transaction.id == transaction_id
    ).first()
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction introuvable")
    return transaction


# ─────────────────────────────────────────────
# FIX 2 : Webhook avec vérification de signature HMAC
# ─────────────────────────────────────────────

def _verify_webhook_signature(raw_body: bytes, signature_header: Optional[str]) -> bool:
    """
    Vérifie la signature HMAC-SHA256 du callback opérateur.
    Retourne True si la signature est valide ou si le secret n'est pas configuré (dev).
    """
    if not settings.WEBHOOK_SECRET or settings.WEBHOOK_SECRET.startswith("CHANGE_ME"):
        logger.warning("WEBHOOK_SECRET non configuré — vérification de signature ignorée")
        return True
    if not signature_header:
        return False
    expected = hmac.new(
        settings.WEBHOOK_SECRET.encode(),
        raw_body,
        hashlib.sha256,
    ).hexdigest()
    # Support format "sha256=<hex>" ou "<hex>" selon l'opérateur
    received = signature_header.replace("sha256=", "").strip()
    return hmac.compare_digest(expected, received)


@router.post("/webhook/callback")
async def webhook_callback(request: Request, db: Session = Depends(get_db)):
    """Reçoit les callbacks des opérateurs de paiement avec vérification de signature."""
    raw_body = await request.body()

    # FIX 2 : vérification HMAC
    signature = request.headers.get("X-Signature") or request.headers.get("X-Webhook-Signature")
    if not _verify_webhook_signature(raw_body, signature):
        logger.warning(f"Signature webhook invalide — IP: {request.client.host}")
        raise HTTPException(status_code=401, detail="Signature invalide")

    try:
        body = json.loads(raw_body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Corps JSON invalide")

    reference = body.get("reference") or body.get("order_id") or body.get("externalId")
    if not reference:
        return {"status": "ignored"}

    transaction = db.query(models.Transaction).filter(
        models.Transaction.reference == reference
    ).first()
    if not transaction:
        return {"status": "not_found"}

    # Re-vérifier le statut auprès de l'opérateur
    if transaction.operator == models.PaymentOperator.ORANGE_MONEY:
        result = await orange_money.check_payment_status(
            transaction.operator_transaction_id or reference
        )
    elif transaction.operator == models.PaymentOperator.MTN_MOMO:
        result = await mtn_momo.check_payment_status(
            transaction.operator_transaction_id or reference
        )
    elif transaction.operator == models.PaymentOperator.WAVE:
        result = await wave.check_payment_status(
            transaction.operator_transaction_id or reference
        )
    else:
        result = {"success": False}

    if result.get("success") and transaction.status != models.TransactionStatus.SUCCESS:
        transaction.status = models.TransactionStatus.SUCCESS
        transaction.completed_at = datetime.utcnow()
        db.commit()
        await publish_payment_success({
            "transaction_id": str(transaction.id),
            "reference": transaction.reference,
            "merchant_id": str(transaction.merchant_id),
            "amount": str(transaction.amount),
            "currency": transaction.currency,
        })

    return {"status": "processed"}
