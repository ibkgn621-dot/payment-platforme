from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import Optional
from decimal import Decimal
from .. import models, schemas
from ..database import get_db
from ..redis_client import cache_wallet_balance, get_cached_balance, invalidate_wallet_cache

router = APIRouter(prefix="/api/v1/wallets", tags=["Wallets"])


@router.post("/", response_model=schemas.WalletResponse, status_code=201)
def create_wallet(data: schemas.WalletCreate, db: Session = Depends(get_db)):
    existing = db.query(models.Wallet).filter(models.Wallet.owner_id == data.owner_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Ce wallet existe déjà")

    wallet = models.Wallet(
        owner_id=data.owner_id,
        owner_type=data.owner_type,
        currency=data.currency,
    )
    db.add(wallet)
    db.commit()
    db.refresh(wallet)
    return wallet


@router.get("/{owner_id}", response_model=schemas.WalletResponse)
def get_wallet(owner_id: str, db: Session = Depends(get_db)):
    wallet = db.query(models.Wallet).filter(models.Wallet.owner_id == owner_id).first()
    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet introuvable")
    return wallet


@router.get("/{owner_id}/balance")
def get_balance(owner_id: str, db: Session = Depends(get_db)):
    # Vérifier le cache d'abord
    cached = get_cached_balance(owner_id)
    if cached:
        return {"cached": True, **cached}

    wallet = db.query(models.Wallet).filter(models.Wallet.owner_id == owner_id).first()
    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet introuvable")

    # Mettre en cache
    cache_wallet_balance(owner_id, float(wallet.balance), float(wallet.available_balance))

    return {
        "cached": False,
        "balance": str(wallet.balance),
        "available": str(wallet.available_balance),
        "frozen": str(wallet.frozen_balance),
        "currency": wallet.currency,
    }


@router.post("/{wallet_id}/credit", response_model=schemas.LedgerResponse)
def credit_wallet(
    wallet_id: str,
    data: schemas.CreditDebitRequest,
    db: Session = Depends(get_db)
):
    wallet = db.query(models.Wallet).filter(models.Wallet.id == wallet_id).with_for_update().first()
    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet introuvable")
    if wallet.status != models.WalletStatus.ACTIVE:
        raise HTTPException(status_code=400, detail="Wallet non actif")

    balance_before = wallet.balance
    wallet.balance += data.amount
    wallet.available_balance += data.amount

    entry = models.WalletLedger(
        wallet_id=wallet.id,
        type=models.LedgerType.CREDIT,
        amount=data.amount,
        reference=data.reference,
        description=data.description,
        balance_before=balance_before,
        balance_after=wallet.balance,
        transaction_id=data.transaction_id,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)

    # Invalider le cache
    invalidate_wallet_cache(str(wallet.owner_id))
    return entry


@router.post("/{wallet_id}/debit", response_model=schemas.LedgerResponse)
def debit_wallet(
    wallet_id: str,
    data: schemas.CreditDebitRequest,
    db: Session = Depends(get_db)
):
    wallet = db.query(models.Wallet).filter(models.Wallet.id == wallet_id).with_for_update().first()
    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet introuvable")
    if wallet.status != models.WalletStatus.ACTIVE:
        raise HTTPException(status_code=400, detail="Wallet non actif")
    if wallet.available_balance < data.amount:
        raise HTTPException(status_code=400, detail="Solde insuffisant")

    balance_before = wallet.balance
    wallet.balance -= data.amount
    wallet.available_balance -= data.amount

    entry = models.WalletLedger(
        wallet_id=wallet.id,
        type=models.LedgerType.DEBIT,
        amount=data.amount,
        reference=data.reference,
        description=data.description,
        balance_before=balance_before,
        balance_after=wallet.balance,
        transaction_id=data.transaction_id,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)

    invalidate_wallet_cache(str(wallet.owner_id))
    return entry


@router.get("/{wallet_id}/ledger", response_model=schemas.LedgerList)
def get_ledger(
    wallet_id: str,
    ledger_type: Optional[models.LedgerType] = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    query = db.query(models.WalletLedger).filter(
        models.WalletLedger.wallet_id == wallet_id
    )
    if ledger_type:
        query = query.filter(models.WalletLedger.type == ledger_type)

    total = query.count()
    items = query.order_by(desc(models.WalletLedger.created_at)).offset(skip).limit(limit).all()
    return schemas.LedgerList(total=total, items=items)
