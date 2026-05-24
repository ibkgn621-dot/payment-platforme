from pydantic import BaseModel
from typing import Optional, List
from uuid import UUID
from datetime import datetime
from .models import RiskLevel, FraudAction

class FraudAnalysisRequest(BaseModel):
    transaction_id: UUID
    reference: str
    merchant_id: Optional[UUID] = None
    phone_number: Optional[str] = None
    amount: float
    currency: str = "GNF"
    operator: Optional[str] = None
    ip_address: Optional[str] = None

class FraudAnalysisResult(BaseModel):
    transaction_id: UUID
    reference: str
    fraud_score: int
    risk_level: RiskLevel
    action: FraudAction
    triggered_rules: List[str]
    is_fraud_suspected: bool

class FraudLogResponse(BaseModel):
    id: UUID
    transaction_id: UUID
    reference: str
    amount: float
    fraud_score: int
    risk_level: RiskLevel
    action: FraudAction
    triggered_rules: Optional[str] = None
    is_confirmed_fraud: bool
    created_at: datetime

    model_config = {"from_attributes": True}

class FraudLogList(BaseModel):
    total: int
    items: List[FraudLogResponse]

class ConfirmFraudRequest(BaseModel):
    is_fraud: bool
    notes: Optional[str] = None
