from pydantic import BaseModel
from typing import Optional, List
from uuid import UUID
from datetime import datetime
from decimal import Decimal
from .models import WalletStatus, LedgerType

class WalletCreate(BaseModel):
    owner_id: UUID
    owner_type: str = "user"
    currency: str = "GNF"

class WalletResponse(BaseModel):
    id: UUID
    owner_id: UUID
    owner_type: str
    currency: str
    balance: Decimal
    available_balance: Decimal
    frozen_balance: Decimal
    status: WalletStatus
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}

class CreditDebitRequest(BaseModel):
    amount: Decimal
    reference: str
    description: Optional[str] = None
    transaction_id: Optional[UUID] = None

class LedgerResponse(BaseModel):
    id: UUID
    wallet_id: UUID
    type: LedgerType
    amount: Decimal
    reference: str
    description: Optional[str] = None
    balance_before: Decimal
    balance_after: Decimal
    created_at: datetime

    model_config = {"from_attributes": True}

class LedgerList(BaseModel):
    total: int
    items: List[LedgerResponse]
