from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, Date, DateTime, Numeric, String

from app.db.base import Base


class PEPProfile(Base):
    __tablename__ = "pep_profiles"

    pep_id = Column(String(20), primary_key=True)
    user_id = Column(String(20), nullable=True)
    role = Column(String(80), nullable=True)
    country = Column(String(2), nullable=True)
    designation_date = Column(Date, nullable=True)
    expiry_date = Column(Date, nullable=True)
    risk_weight_multiplier = Column(Numeric(4, 2), nullable=True, default=1.5)
    source = Column(String(60), nullable=True)
    last_verified = Column(Date, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
