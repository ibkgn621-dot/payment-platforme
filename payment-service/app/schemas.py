from pydantic import BaseModel, field_validator
from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import datetime
from decimal import Decimal
from .models import TransactionStatus, PaymentOperator

class PaymentCreate(BaseModel):
    merchant_id: UUID
    amount: Decimal
    currency: str = "GNF"
    operator: PaymentOperator
    phone_number: str
    description: Optional[str] = None
    callback_url: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    @field_validator("amount")
    @classmethod
    def amount_must_be_positive(cls, v):
        if v <= 0:
            raise ValueError("Le montant doit être positif")
        return v

    @field_validator("phone_number")
    @classmethod
    def phone_format(cls, v):
        v = v.replace(" ", "").replace("-", "")
        if not v.startswith("+"):
            v = "+224" + v.lstrip("0")
        return v

class PaymentVerify(BaseModel):
    reference: str

class TransactionResponse(BaseModel):
    id: UUID
    reference: str
    merchant_id: UUID
    amount: Decimal
    currency: str
    operator: PaymentOperator
    phone_number: Optional[str] = None
    status: TransactionStatus
    fees: Decimal
    net_amount: Optional[Decimal] = None
    description: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}

class TransactionList(BaseModel):
    total: int
    items: List[TransactionResponse]

class WebhookCreate(BaseModel):
    merchant_id: UUID
    url: str
    secret: str
    events: List[str]
