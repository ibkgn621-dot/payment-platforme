from sqlalchemy import Column, String, Numeric, Boolean, DateTime, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid
import enum
from .database import Base

class WalletStatus(str, enum.Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    CLOSED = "closed"

class LedgerType(str, enum.Enum):
    CREDIT = "credit"
    DEBIT = "debit"

class Wallet(Base):
    __tablename__ = "wallets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id = Column(UUID(as_uuid=True), nullable=False, unique=True, index=True)
    owner_type = Column(String(20), default="user")  # user / merchant
    currency = Column(String(3), default="GNF", nullable=False)
    balance = Column(Numeric(20, 2), default=0, nullable=False)
    available_balance = Column(Numeric(20, 2), default=0, nullable=False)
    frozen_balance = Column(Numeric(20, 2), default=0, nullable=False)
    status = Column(SAEnum(WalletStatus), default=WalletStatus.ACTIVE)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class WalletLedger(Base):
    __tablename__ = "wallet_ledger"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    wallet_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    type = Column(SAEnum(LedgerType), nullable=False)
    amount = Column(Numeric(20, 2), nullable=False)
    reference = Column(String(100), nullable=False, index=True)
    description = Column(String(255), nullable=True)
    balance_before = Column(Numeric(20, 2), nullable=False)
    balance_after = Column(Numeric(20, 2), nullable=False)
    transaction_id = Column(UUID(as_uuid=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
