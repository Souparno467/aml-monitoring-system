from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import relationship

from app.db.base import Base


class Alert(Base):
    __tablename__ = "alerts"

    alert_id = Column(String(20), primary_key=True)
    txn_id = Column(String(20), ForeignKey("transactions.txn_id"), nullable=True)
    user_id = Column(String(20), ForeignKey("users.user_id"), nullable=True)
    alert_rule = Column(String(60), nullable=True)
    severity = Column(String(20), nullable=True, default="MEDIUM")
    composite_risk_score = Column(Numeric(5, 4), nullable=True)
    rule_score = Column(Numeric(5, 4), nullable=True)
    ml_score = Column(Numeric(5, 4), nullable=True)
    graph_score = Column(Numeric(5, 4), nullable=True)
    alert_created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    alert_resolved_at = Column(DateTime(timezone=True), nullable=True)
    resolution_time_hours = Column(Numeric(8, 2), nullable=True)
    assigned_analyst = Column(String(60), nullable=True)
    alert_status = Column(String(40), nullable=True, default="Open")
    sar_filed = Column(Boolean, nullable=True, default=False)
    false_positive = Column(Boolean, nullable=True, default=False)
    notes = Column(Text, nullable=True)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    transaction = relationship("Transaction", back_populates="alert")
    user = relationship("User", back_populates="alerts")
