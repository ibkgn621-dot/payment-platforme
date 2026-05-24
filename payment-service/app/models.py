from sqlalchemy import Column, String, Numeric, Boolean, DateTime, Enum as SAEnum, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid
import enum
from .database import Base

class TransactionStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"

class PaymentOperator(str, enum.Enum):
    ORANGE_MONEY = "orange_money"
    MTN_MOMO = "mtn_momo"
    WAVE = "wave"
    VISA = "visa"
    MASTERCARD = "mastercard"

class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    reference = Column(String(50), unique=True, nullable=False, index=True)
    merchant_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    amount = Column(Numeric(20, 2), nullable=False)
    currency = Column(String(3), default="GNF", nullable=False)
    operator = Column(SAEnum(PaymentOperator), nullable=False)
    phone_number = Column(String(20), nullable=True)
    status = Column(SAEnum(TransactionStatus), default=TransactionStatus.PENDING, nullable=False)
    operator_transaction_id = Column(String(100), nullable=True)
    description = Column(String(255), nullable=True)
    metadata = Column(Text, nullable=True)   # JSON string
    fees = Column(Numeric(20, 2), default=0)
    net_amount = Column(Numeric(20, 2), nullable=True)
    error_message = Column(String(500), nullable=True)
    callback_url = Column(String(500), nullable=True)
    ip_address = Column(String(45), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)

class Webhook(Base):
    __tablename__ = "webhooks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    merchant_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    url = Column(String(500), nullable=False)
    secret = Column(String(100), nullable=False)
    events = Column(Text, nullable=False)   # JSON array
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
