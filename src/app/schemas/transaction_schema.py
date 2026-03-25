from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field


class TransactionCreate(BaseModel):
    txn_id: str
    sender_id: str
    receiver_id: str
    amount_usd: float
    amount_local: float
    currency: str
    fx_rate_to_usd: float = 1.0
    payment_method: Optional[str] = None
    txn_type: Optional[str] = None
    timestamp: datetime
    is_cross_border: bool = False
    sender_country: Optional[str] = None
    receiver_country: Optional[str] = None
    device_fingerprint: Optional[str] = None
    ip_country: Optional[str] = None
    channel: Optional[str] = None


class TransactionOut(BaseModel):
    txn_id: str
    sender_id: str
    receiver_id: str
    amount_usd: float
    composite_risk_score: float = 0.0
    risk_label: str = "LOW"

    class Config:
        from_attributes = True


class TransactionListOut(BaseModel):
    total: int
    results: list[TransactionOut]


class TransactionScoreIn(BaseModel):
    """Score a transaction without persisting it and without requiring entity IDs."""

    amount_usd: float = Field(default=2500, ge=0)
    currency: str = Field(default="USD", min_length=1, max_length=6)
    payment_method: Optional[str] = None
    txn_type: Optional[str] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    is_cross_border: bool = False
    sender_country: Optional[str] = None
    receiver_country: Optional[str] = None
    ip_country: Optional[str] = None
    channel: Optional[str] = None

    pep_involved: bool = False
    dormant_days: int = Field(default=0, ge=0)
    recent_txn_count: int = Field(default=0, ge=0)
    recent_total_usd: float = Field(default=0.0, ge=0)
    graph_score: float = Field(default=0.0, ge=0.0, le=1.0)


class TransactionScoreOut(BaseModel):
    composite_risk_score: float
    risk_label: str
    severity: Optional[str] = None
    alert_recommended: bool = False

    rule_score: float
    ml_score: float
    graph_score: float

    ml_model_loaded: bool = False
    is_cross_border_used: bool = False
    data_warnings: list[str] = []

    triggered_rules: list[str] = []
    reasons: list[str] = []

