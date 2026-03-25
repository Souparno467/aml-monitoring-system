from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

from app.config import settings


def _classify(score: float) -> str:
    if score >= 0.80:
        return "CRITICAL"
    if score >= settings.RISK_SCORE_HIGH_THRESHOLD:
        return "HIGH"
    if score >= settings.RISK_SCORE_MEDIUM_THRESHOLD:
        return "MEDIUM"
    return "LOW"


def audit_transactions_csv(max_rows: int = 200000) -> dict[str, Any]:
    data_path = settings.resolve_path(settings.DATA_DIR) / "transactions.csv"
    if not data_path.exists():
        return {"ok": False, "error": f"missing {data_path}"}

    try:
        import pandas as pd  # type: ignore
    except Exception:
        return {"ok": False, "error": "pandas not installed"}

    df = pd.read_csv(data_path)
    if max_rows and len(df) > int(max_rows):
        df = df.head(int(max_rows)).copy()

    needed = ["rule_score", "ml_score", "graph_score", "composite_risk_score"]
    for c in needed:
        if c not in df.columns:
            return {"ok": False, "error": f"transactions.csv missing column {c}"}

    rule = df["rule_score"].astype(float)
    ml = df["ml_score"].astype(float)
    graph = df["graph_score"].astype(float)
    comp = df["composite_risk_score"].astype(float)

    calc = (
        rule * float(settings.RULE_SCORE_WEIGHT)
        + ml * float(settings.ML_SCORE_WEIGHT)
        + graph * float(settings.GRAPH_SCORE_WEIGHT)
    ).clip(lower=0.0, upper=1.0)

    abs_err = (calc - comp).abs()

    label_mismatch = None
    if "risk_label" in df.columns:
        expected = calc.apply(_classify)
        actual = df["risk_label"].astype(str).str.upper()
        label_mismatch = int((expected != actual).sum())

    return {
        "ok": True,
        "path": str(data_path),
        "rows": int(len(df)),
        "weights_used": {
            "rule": float(settings.RULE_SCORE_WEIGHT),
            "ml": float(settings.ML_SCORE_WEIGHT),
            "graph": float(settings.GRAPH_SCORE_WEIGHT),
        },
        "composite_error": {
            "mean_abs": float(abs_err.mean()),
            "p95_abs": float(abs_err.quantile(0.95)),
            "max_abs": float(abs_err.max()),
            "within_0_01": float((abs_err <= 0.01).mean()),
            "within_0_05": float((abs_err <= 0.05).mean()),
        },
        "risk_label_mismatch": label_mismatch,
    }


def audit_alerts_csv(max_rows: int = 200000) -> dict[str, Any]:
    data_path = settings.resolve_path(settings.DATA_DIR) / "alerts.csv"
    if not data_path.exists():
        return {"ok": False, "error": f"missing {data_path}"}

    try:
        import pandas as pd  # type: ignore
    except Exception:
        return {"ok": False, "error": "pandas not installed"}

    df = pd.read_csv(data_path)
    if max_rows and len(df) > int(max_rows):
        df = df.head(int(max_rows)).copy()

    required = ["alert_created_at", "alert_resolved_at", "resolution_time_hours", "alert_status", "sar_filed", "false_positive"]
    for c in required:
        if c not in df.columns:
            return {"ok": False, "error": f"alerts.csv missing column {c}"}

    created = pd.to_datetime(df["alert_created_at"], errors="coerce", utc=True)
    resolved = pd.to_datetime(df["alert_resolved_at"], errors="coerce", utc=True)

    # recompute where possible
    delta_hours = (resolved - created).dt.total_seconds() / 3600.0
    delta_hours = delta_hours.where(delta_hours >= 0)

    existing = pd.to_numeric(df["resolution_time_hours"], errors="coerce")
    comparable = delta_hours.notna() & existing.notna()
    mismatch = int(((delta_hours[comparable] - existing[comparable]).abs() > 0.01).sum())

    status = df["alert_status"].astype(str).str.lower()
    sar = df["sar_filed"].astype(bool)
    fp = df["false_positive"].astype(bool)

    closed = status.str.startswith("closed")
    closed_missing_resolved = int((closed & resolved.isna()).sum())

    sar_in_status = status.str.contains("sar")
    fp_in_status = status.str.contains("false") & status.str.contains("positive")

    sar_inconsistent = int((sar_in_status & (~sar)).sum())
    fp_inconsistent = int((fp_in_status & (~fp)).sum())

    alert_comp = None
    if all(c in df.columns for c in ["rule_score", "ml_score", "graph_score", "composite_risk_score"]):
        rule = pd.to_numeric(df["rule_score"], errors="coerce").fillna(0).astype(float)
        ml = pd.to_numeric(df["ml_score"], errors="coerce").fillna(0).astype(float)
        graph = pd.to_numeric(df["graph_score"], errors="coerce").fillna(0).astype(float)
        comp = pd.to_numeric(df["composite_risk_score"], errors="coerce").fillna(0).astype(float)
        calc = (
            rule * float(settings.RULE_SCORE_WEIGHT)
            + ml * float(settings.ML_SCORE_WEIGHT)
            + graph * float(settings.GRAPH_SCORE_WEIGHT)
        ).clip(lower=0.0, upper=1.0)
        abs_err = (calc - comp).abs()
        alert_comp = {
            "mean_abs": float(abs_err.mean()),
            "p95_abs": float(abs_err.quantile(0.95)),
            "max_abs": float(abs_err.max()),
            "within_0_01": float((abs_err <= 0.01).mean()),
        }

    return {
        "ok": True,
        "path": str(data_path),
        "rows": int(len(df)),
        "resolution_time": {
            "rows_comparable": int(comparable.sum()),
            "mismatched": mismatch,
        },
        "alert_composite_error": alert_comp,
        "status_consistency": {
            "closed_missing_resolved_at": closed_missing_resolved,
            "sar_in_status_but_sar_filed_false": sar_inconsistent,
            "false_positive_in_status_but_false_positive_false": fp_inconsistent,
        },
    }


def audit_dataset(max_rows: int = 200000) -> dict[str, Any]:
    return {
        "transactions": audit_transactions_csv(max_rows=max_rows),
        "alerts": audit_alerts_csv(max_rows=max_rows),
    }
