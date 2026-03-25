from __future__ import annotations

from sqlalchemy import Boolean, Column, Date, Numeric, String

from app.db.base import Base


class CountryRisk(Base):
    __tablename__ = "country_risk"

    country_code = Column(String(2), primary_key=True)
    risk_level = Column(String(20), nullable=False)
    risk_score_0_100 = Column(Numeric(5, 1), nullable=True)
    fatf_greylist = Column(Boolean, nullable=True, default=False)
    fatf_blacklist = Column(Boolean, nullable=True, default=False)
    ofac_sanctions = Column(Boolean, nullable=True, default=False)
    corruption_index = Column(Numeric(5, 1), nullable=True)
    aml_deficiency_flag = Column(Boolean, nullable=True, default=False)
    last_updated = Column(Date, nullable=True)
