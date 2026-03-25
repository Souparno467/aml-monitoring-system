from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Numeric, String

from app.db.base import Base


class RiskScore(Base):
    __tablename__ = "risk_scores"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    entity_type = Column(String(20), nullable=False)  # transaction | user
    entity_id = Column(String(20), nullable=False)
    rule_score = Column(Numeric(5, 4), nullable=True)
    ml_score = Column(Numeric(5, 4), nullable=True)
    graph_score = Column(Numeric(5, 4), nullable=True)
    final_score = Column(Numeric(5, 4), nullable=False)
    risk_level = Column(String(20), nullable=False)
    scored_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    model_version = Column(String(20), nullable=True, default="v1")
