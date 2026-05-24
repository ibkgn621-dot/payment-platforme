from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, Text, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid
import enum
from .database import Base

class RiskLevel(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class FraudAction(str, enum.Enum):
    ALLOW = "allow"
    REVIEW = "review"
    BLOCK = "block"

class FraudLog(Base):
    __tablename__ = "fraud_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    transaction_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    reference = Column(String(100), nullable=False, index=True)
    merchant_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    phone_number = Column(String(30), nullable=True)
    amount = Column(Float, nullable=False)
    currency = Column(String(3), default="GNF")
    operator = Column(String(30), nullable=True)
    ip_address = Column(String(45), nullable=True)

    # Résultat de l'analyse
    fraud_score = Column(Integer, default=0)  # 0-100
    risk_level = Column(SAEnum(RiskLevel), default=RiskLevel.LOW)
    action = Column(SAEnum(FraudAction), default=FraudAction.ALLOW)

    # Règles déclenchées
    triggered_rules = Column(Text, nullable=True)  # JSON array
    notes = Column(Text, nullable=True)

    is_confirmed_fraud = Column(Boolean, default=False)
    reviewed_by = Column(UUID(as_uuid=True), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

class FraudRule(Base):
    __tablename__ = "fraud_rules"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False, unique=True)
    description = Column(String(500), nullable=True)
    score_impact = Column(Integer, default=10)   # Points ajoutés au score si déclenchée
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
