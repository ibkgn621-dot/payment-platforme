from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import Optional
import json
from datetime import datetime
from .. import models, schemas
from ..database import get_db
from ..detector import detector

router = APIRouter(prefix="/api/v1/fraud", tags=["Fraud Detection"])


@router.post("/analyze", response_model=schemas.FraudAnalysisResult)
def analyze_transaction(
    request: schemas.FraudAnalysisRequest,
    db: Session = Depends(get_db)
):
    """Analyse une transaction pour détecter une fraude potentielle"""
    score, triggered_rules = detector.analyze({
        "amount": request.amount,
        "phone_number": request.phone_number,
        "ip_address": request.ip_address,
        "reference": request.reference,
    })

    risk_level = detector.get_risk_level(score)
    action = detector.get_action(score)

    # Enregistrer le log
    fraud_log = models.FraudLog(
        transaction_id=request.transaction_id,
        reference=request.reference,
        merchant_id=request.merchant_id,
        phone_number=request.phone_number,
        amount=request.amount,
        currency=request.currency,
        operator=request.operator,
        ip_address=request.ip_address,
        fraud_score=score,
        risk_level=risk_level,
        action=action,
        triggered_rules=json.dumps(triggered_rules),
    )
    db.add(fraud_log)
    db.commit()

    return schemas.FraudAnalysisResult(
        transaction_id=request.transaction_id,
        reference=request.reference,
        fraud_score=score,
        risk_level=risk_level,
        action=action,
        triggered_rules=triggered_rules,
        is_fraud_suspected=(action == "block"),
    )


@router.get("/logs", response_model=schemas.FraudLogList)
def list_fraud_logs(
    risk_level: Optional[models.RiskLevel] = None,
    action: Optional[models.FraudAction] = None,
    confirmed_fraud: Optional[bool] = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    query = db.query(models.FraudLog)
    if risk_level:
        query = query.filter(models.FraudLog.risk_level == risk_level)
    if action:
        query = query.filter(models.FraudLog.action == action)
    if confirmed_fraud is not None:
        query = query.filter(models.FraudLog.is_confirmed_fraud == confirmed_fraud)

    total = query.count()
    items = query.order_by(desc(models.FraudLog.created_at)).offset(skip).limit(limit).all()
    return schemas.FraudLogList(total=total, items=items)


@router.get("/logs/{log_id}", response_model=schemas.FraudLogResponse)
def get_fraud_log(log_id: str, db: Session = Depends(get_db)):
    log = db.query(models.FraudLog).filter(models.FraudLog.id == log_id).first()
    if not log:
        raise HTTPException(status_code=404, detail="Log introuvable")
    return log


@router.patch("/logs/{log_id}/confirm")
def confirm_fraud(
    log_id: str,
    request: schemas.ConfirmFraudRequest,
    db: Session = Depends(get_db)
):
    log = db.query(models.FraudLog).filter(models.FraudLog.id == log_id).first()
    if not log:
        raise HTTPException(status_code=404, detail="Log introuvable")

    log.is_confirmed_fraud = request.is_fraud
    log.notes = request.notes
    log.reviewed_at = datetime.utcnow()
    db.commit()

    # Si fraude confirmée, blacklister le numéro
    if request.is_fraud and log.phone_number:
        detector.add_to_blacklist(phone=log.phone_number, ip=log.ip_address)

    return {"message": "Log mis à jour", "is_confirmed_fraud": request.is_fraud}


@router.post("/blacklist/add")
def add_to_blacklist(
    phone: Optional[str] = None,
    ip: Optional[str] = None
):
    if not phone and not ip:
        raise HTTPException(status_code=400, detail="Fournir phone ou ip")
    detector.add_to_blacklist(phone=phone, ip=ip)
    return {"message": "Ajouté à la blacklist"}


@router.post("/blacklist/remove")
def remove_from_blacklist(
    phone: Optional[str] = None,
    ip: Optional[str] = None
):
    if not phone and not ip:
        raise HTTPException(status_code=400, detail="Fournir phone ou ip")
    detector.remove_from_blacklist(phone=phone, ip=ip)
    return {"message": "Retiré de la blacklist"}
