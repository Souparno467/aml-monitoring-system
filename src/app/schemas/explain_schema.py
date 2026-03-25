from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel


class ScoreComponentOut(BaseModel):
    score: float
    weight: float
    contribution: float


class ScoreBreakdownOut(BaseModel):
    rule: ScoreComponentOut
    ml: ScoreComponentOut
    graph: ScoreComponentOut


class FeatureHighlightOut(BaseModel):
    label: str
    value: str
    why: Optional[str] = None


class RiskExplainOut(BaseModel):
    entity_type: str
    entity_id: str
    risk_label: Optional[str] = None
    composite_risk_score: Optional[float] = None
    breakdown: Optional[ScoreBreakdownOut] = None
    triggered_rules: list[str] = []
    reasons: list[str] = []
    highlights: list[FeatureHighlightOut] = []
