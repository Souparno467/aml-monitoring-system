from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class RiskModelInfoOut(BaseModel):
    loaded: bool
    model: Optional[str] = None
    model_type: Optional[str] = None
    feature_names: Optional[list[str]] = None
    load_error: Optional[str] = None


class MetricOut(BaseModel):
    roc_auc: float | None = None
    average_precision: float | None = None


class RiskEvaluateIn(BaseModel):
    max_rows: int = Field(default=50000, ge=100, le=500000)
    top_n: int = Field(default=20, ge=0, le=200)
    split_strategy: str = Field(default="time")
    test_size: float = Field(default=0.2, ge=0.05, le=0.5)
    random_state: int = Field(default=42, ge=0, le=10_000)


class RiskEvaluateOut(BaseModel):
    split_strategy: str = "time"
    cutoff_timestamp: str | None = None
    train_rows: int | None = None
    test_rows: int | None = None
    rows: int
    positives: int
    prevalence: float
    ml: MetricOut
    composite: MetricOut
    top: list[dict[str, Any]]
    notes: list[str] = []


class RiskTrainIn(BaseModel):
    max_rows: int = Field(default=200000, ge=1000, le=5000000)
    split_strategy: str = Field(default="time")
    test_size: float = Field(default=0.2, ge=0.05, le=0.5)
    random_state: int = Field(default=42, ge=0, le=10_000)


class RiskTrainOut(BaseModel):
    model: str
    split_strategy: str = "time"
    cutoff_timestamp: str | None = None
    train_rows: int | None = None
    test_rows: int | None = None
    rows: int
    positives: int
    prevalence: float
    ml: MetricOut
    feature_columns: list[str]
    notes: list[str] = []

