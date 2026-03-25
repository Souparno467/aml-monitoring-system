from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, Date, DateTime, Integer, Numeric, String
from sqlalchemy.orm import relationship

from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    user_id = Column(String(20), primary_key=True)
    account_type = Column(String(20), nullable=False, default="Individual")
    country = Column(String(2), nullable=False)
    occupation = Column(String(60), nullable=True)
    kyc_level = Column(String(20), nullable=False, default="Partial")
    is_pep = Column(Boolean, nullable=False, default=False)
    account_created_date = Column(Date, nullable=True)
    last_active_date = Column(Date, nullable=True)
    dormant_days_before_activation = Column(Integer, nullable=True, default=0)
    avg_monthly_txn_volume_usd = Column(Numeric(18, 4), nullable=True)
    credit_score = Column(Integer, nullable=True)
    num_linked_accounts = Column(Integer, nullable=True, default=1)
    sanctions_hit = Column(Boolean, nullable=True, default=False)
    adverse_media_flag = Column(Boolean, nullable=True, default=False)
    industry = Column(String(80), nullable=True)
    risk_tier = Column(String(20), nullable=False, default="LOW")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    sent_transactions = relationship(
        "Transaction", foreign_keys="Transaction.sender_id", back_populates="sender"
    )
    received_transactions = relationship(
        "Transaction", foreign_keys="Transaction.receiver_id", back_populates="receiver"
    )
    alerts = relationship("Alert", back_populates="user")
    graph_node = relationship("GraphNode", back_populates="user", uselist=False)
