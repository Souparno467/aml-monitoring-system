from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class AlertOut(BaseModel):
    alert_id: str
    txn_id: Optional[str] = None
    user_id: Optional[str] = None
    alert_rule: Optional[str] = None
    severity: Optional[str] = None
    composite_risk_score: Optional[float] = None
    rule_score: Optional[float] = None
    ml_score: Optional[float] = None
    graph_score: Optional[float] = None
    alert_created_at: Optional[datetime] = None
    alert_resolved_at: Optional[datetime] = None
    resolution_time_hours: Optional[float] = None
    assigned_analyst: Optional[str] = None
    alert_status: Optional[str] = None
    sar_filed: Optional[bool] = None
    false_positive: Optional[bool] = None
    notes: Optional[str] = None

    class Config:
        from_attributes = True


class AlertListOut(BaseModel):
    total: int
    results: list[AlertOut]


class AlertUpdate(BaseModel):
    alert_status: Optional[str] = None
    notes: Optional[str] = None
    sar_filed: Optional[bool] = None
    false_positive: Optional[bool] = None
