from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import relationship

from app.db.base import Base


class Transaction(Base):
    __tablename__ = "transactions"

    txn_id = Column(String(20), primary_key=True)
    sender_id = Column(String(20), ForeignKey("users.user_id"), nullable=False)
    receiver_id = Column(String(20), ForeignKey("users.user_id"), nullable=False)
    amount_usd = Column(Numeric(18, 4), nullable=False)
    amount_local = Column(Numeric(18, 4), nullable=False)
    currency = Column(String(3), nullable=False)
    fx_rate_to_usd = Column(Numeric(14, 6), nullable=True, default=1)
    payment_method = Column(String(20), nullable=True)
    txn_type = Column(String(30), nullable=True)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    hour_of_day = Column(Numeric(4, 0), nullable=True)
    day_of_week = Column(String(10), nullable=True)
    is_weekend = Column(Boolean, nullable=True, default=False)
    is_cross_border = Column(Boolean, nullable=True, default=False)
    sender_country = Column(String(2), nullable=True)
    receiver_country = Column(String(2), nullable=True)
    transaction_fee_usd = Column(Numeric(12, 4), nullable=True)

    flag_large_transaction = Column(Boolean, nullable=True, default=False)
    flag_high_risk_country = Column(Boolean, nullable=True, default=False)
    flag_pep_involved = Column(Boolean, nullable=True, default=False)
    flag_structuring = Column(Boolean, nullable=True, default=False)
    flag_dormant_account = Column(Boolean, nullable=True, default=False)
    flag_crypto = Column(Boolean, nullable=True, default=False)
    flag_night_transaction = Column(Boolean, nullable=True, default=False)
    flag_round_amount = Column(Boolean, nullable=True, default=False)

    rule_score = Column(Numeric(5, 4), nullable=True, default=0)
    ml_score = Column(Numeric(5, 4), nullable=True, default=0)
    graph_score = Column(Numeric(5, 4), nullable=True, default=0)
    composite_risk_score = Column(Numeric(5, 4), nullable=True, default=0)
    risk_label = Column(String(20), nullable=True, default="LOW")

    pattern_type = Column(String(30), nullable=True, default="normal")
    is_sar_filed = Column(Boolean, nullable=True, default=False)
    status = Column(String(20), nullable=True, default="Pending")
    device_fingerprint = Column(String(32), nullable=True)
    ip_country = Column(String(2), nullable=True)
    channel = Column(String(30), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    sender = relationship("User", foreign_keys=[sender_id], back_populates="sent_transactions")
    receiver = relationship("User", foreign_keys=[receiver_id], back_populates="received_transactions")
    alert = relationship("Alert", back_populates="transaction", uselist=False)
