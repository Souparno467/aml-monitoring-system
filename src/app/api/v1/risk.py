from __future__ import annotations

from fastapi import APIRouter, Body, HTTPException

from app.config import settings
from app.ml.predict import ml_predictor
from app.ml.train import train_xgb_from_csv
from app.ml.train import _default_feature_columns
from app.schemas.risk_schema import (
    MetricOut,
    RiskEvaluateIn,
    RiskEvaluateOut,
    RiskModelInfoOut,
    RiskTrainIn,
    RiskTrainOut,
)

router = APIRouter()

_FORBIDDEN_FEATURES: set[str] = {
    "is_sar_filed",
    "ml_score",
    "composite_risk_score",
    "risk_label",
    "_ts",
}


def _require_debug() -> None:
    """Enable training/evaluation only for local development (DEBUG=true)."""
    if settings.DEBUG:
        return
    # Don't reveal that the endpoint exists.
    raise HTTPException(status_code=404, detail="Not found")



def _feature_groups(model, feature_names: list[str]) -> tuple[set[str], set[str]]:
    """Best-effort (numeric_cols, categorical_cols) from the fitted pipeline."""
    numeric: set[str] = set()
    categorical: set[str] = set()

    try:
        steps = getattr(model, "named_steps", None)
        pre = steps.get("pre") if isinstance(steps, dict) else None
        transformers = getattr(pre, "transformers", None)
        if transformers:
            for name, _transformer, cols in list(transformers):
                if not cols:
                    continue
                col_set = {str(c) for c in cols}
                if name == "cat":
                    categorical |= col_set
                elif name == "num":
                    numeric |= col_set
    except Exception:
        numeric = set()
        categorical = set()

    if not numeric and not categorical:
        n, c = _default_feature_columns(list(feature_names))
        numeric = set(n)
        categorical = set(c)

    allowed = set(feature_names)
    return numeric & allowed, categorical & allowed



def _feature_names(model) -> list[str] | None:
    raw = getattr(model, "feature_names_in_", None)
    if raw is None:
        return None
    try:
        names = list(raw)
    except Exception:
        return None
    return names or None


@router.get("/model", response_model=RiskModelInfoOut)
async def model_info():
    load_error = None
    try:
        ml_predictor._load()  # type: ignore[attr-defined]
    except Exception as exc:
        load_error = f"model_load_failed:{exc.__class__.__name__}"

    model = getattr(ml_predictor, "_xgb", None)
    loaded = model is not None

    model_type = type(model).__name__ if loaded else None
    feature_names = _feature_names(model) if loaded else None

    # only expose filename (no local filesystem path)
    model_name = "xgb_aml_v1.joblib" if settings.resolve_path(settings.ML_MODEL_PATH).joinpath("xgb_aml_v1.joblib").exists() else None

    return {
        "loaded": bool(loaded),
        "debug": bool(settings.DEBUG),
        "model": model_name,
        "model_type": model_type,
        "feature_names": feature_names,
        "load_error": load_error if settings.DEBUG else None,
    }


@router.post("/model/train", response_model=RiskTrainOut)
async def train_model(payload: RiskTrainIn = Body(default=RiskTrainIn())):
    _require_debug()

    res = train_xgb_from_csv(
        max_rows=int(payload.max_rows) if payload.max_rows else None,
        test_size=float(payload.test_size),
        random_state=int(payload.random_state),
        split_strategy=str(payload.split_strategy or "time"),
    )

    try:
        ml_predictor.reset()
        ml_predictor._load()  # type: ignore[attr-defined]
    except Exception:
        pass

    return {
        "model": "xgb_aml_v1.joblib",
        "split_strategy": str(res.split_strategy),
        "cutoff_timestamp": res.cutoff_timestamp,
        "train_rows": int(res.train_rows),
        "test_rows": int(res.test_rows),
        "rows": int(res.rows),
        "positives": int(res.positives),
        "prevalence": float(res.prevalence),
        "ml": {"roc_auc": res.roc_auc, "average_precision": res.average_precision},
        "feature_columns": list(res.feature_columns),
        "notes": list(res.notes or []),
    }


@router.post("/model/reset", response_model=RiskTrainOut)
async def reset_model():
    """Reset model to the default trained baseline.

    Portfolio convenience: retrains and overwrites the current model file.
    """
    _require_debug()

    res = train_xgb_from_csv(max_rows=200000, test_size=0.2, random_state=42, split_strategy="time")

    try:
        ml_predictor.reset()
        ml_predictor._load()  # type: ignore[attr-defined]
    except Exception:
        pass

    return {
        "model": "xgb_aml_v1.joblib",
        "split_strategy": str(res.split_strategy),
        "cutoff_timestamp": res.cutoff_timestamp,
        "train_rows": int(res.train_rows),
        "test_rows": int(res.test_rows),
        "rows": int(res.rows),
        "positives": int(res.positives),
        "prevalence": float(res.prevalence),
        "ml": {"roc_auc": res.roc_auc, "average_precision": res.average_precision},
        "feature_columns": list(res.feature_columns),
        "notes": ["reset: trained with defaults max_rows=200000 test_size=0.2 random_state=42"],
    }


@router.post("/evaluate", response_model=RiskEvaluateOut)
async def evaluate(payload: RiskEvaluateIn = Body(default=RiskEvaluateIn())):
    _require_debug()

    data_path = settings.resolve_path(settings.DATA_DIR) / "transactions.csv"
    if not data_path.exists():
        raise HTTPException(status_code=404, detail=f"Dataset not found")

    try:
        import pandas as pd  # type: ignore
    except Exception:
        raise HTTPException(status_code=501, detail="pandas is required")

    df = pd.read_csv(data_path)
    if payload.max_rows and len(df) > payload.max_rows:
        df = df.head(int(payload.max_rows)).copy()

    if "is_sar_filed" not in df.columns:
        raise HTTPException(status_code=400, detail="Dataset missing is_sar_filed")
    notes: list[str] = []

    # holdout split (default: time-based)
    strat = str(getattr(payload, 'split_strategy', 'time') or 'time').strip().lower()
    test_size = float(getattr(payload, 'test_size', 0.2) or 0.2)
    random_state = int(getattr(payload, 'random_state', 42) or 42)

    split_strategy = strat
    cutoff_ts = None
    train_rows = None
    test_rows = None

    if strat == 'time' and 'timestamp' in df.columns and len(df) > 10:
        ts = pd.to_datetime(df['timestamp'], errors='coerce', utc=True)
        df = df.assign(_ts=ts).dropna(subset=['_ts']).sort_values('_ts')
        n = len(df)
        split_at = max(1, min(n - 1, int(round((1.0 - test_size) * n))))
        cutoff_ts = df.iloc[split_at - 1]['_ts'].isoformat()
        df_test = df.iloc[split_at:].copy()
        df_train = df.iloc[:split_at].copy()
        train_rows = int(len(df_train))
        test_rows = int(len(df_test))
        notes.append(f'Time split: test_size={test_size}')
    elif strat in {'random', 'rand'}:
        # Random holdout for quick experiments (uses pandas sampling).
        df_test = df.sample(frac=test_size, random_state=random_state).copy()
        df_train = df.drop(index=df_test.index).copy()
        train_rows = int(len(df_train))
        test_rows = int(len(df_test))
        split_strategy = 'random'
        notes.append(f'Random split: test_size={test_size} random_state={random_state}')
    else:
        df_test = df
        df_train = None
        split_strategy = 'none'
        train_rows = None
        test_rows = int(len(df_test))

    y_true = df_test["is_sar_filed"].astype(int)

    try:
        ml_predictor._load()  # type: ignore[attr-defined]
    except Exception:
        pass

    model = getattr(ml_predictor, "_xgb", None)
    model_loaded = model is not None


    if model_loaded:
        feature_names = _feature_names(model) or []
        if not feature_names:
            default_numeric, default_categorical = _default_feature_columns(list(df_test.columns))
            feature_names = list(default_numeric) + list(default_categorical)
            notes.append("Model missing feature_names_in_; used default feature columns")

        bad = sorted(set(feature_names) & _FORBIDDEN_FEATURES)
        if bad:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Feature leakage detected in evaluation. "
                    f"Remove these columns from features: {bad}"
                ),
            )

        X = df_test.copy()
        numeric_cols, categorical_cols = _feature_groups(model, feature_names)
        for c in feature_names:
            if c not in X.columns:
                X[c] = "" if c in categorical_cols else 0
        X = X[feature_names]
        for c in X.columns:
            if c in categorical_cols:
                X[c] = X[c].fillna("").astype(str)
            else:
                X[c] = pd.to_numeric(X[c], errors="coerce").fillna(0)

        y_ml = model.predict_proba(X)[:, 1]
    else:
        if "ml_score" in df_test.columns:
            y_ml = df_test["ml_score"].astype(float)
            notes.append("Model not loaded; used dataset ml_score")
        else:
            y_ml = df_test.get("rule_score", 0).astype(float) * 0
            notes.append("Model not loaded; ml_score set to 0")

    if "composite_risk_score" in df_test.columns:
        y_comp = df_test["composite_risk_score"].astype(float)
    else:
        rule = df_test.get("rule_score", 0).astype(float)
        graph = df_test.get("graph_score", 0).astype(float)
        y_comp = (
            rule * settings.RULE_SCORE_WEIGHT
            + y_ml * settings.ML_SCORE_WEIGHT
            + graph * settings.GRAPH_SCORE_WEIGHT
        )

    try:
        from sklearn.metrics import average_precision_score, roc_auc_score  # type: ignore

        ml_metrics = MetricOut(
            roc_auc=float(roc_auc_score(y_true, y_ml)) if y_true.nunique() > 1 else None,
            average_precision=float(average_precision_score(y_true, y_ml)) if y_true.nunique() > 1 else None,
        )
        comp_metrics = MetricOut(
            roc_auc=float(roc_auc_score(y_true, y_comp)) if y_true.nunique() > 1 else None,
            average_precision=float(average_precision_score(y_true, y_comp)) if y_true.nunique() > 1 else None,
        )
    except Exception:
        raise HTTPException(status_code=501, detail="scikit-learn required")

    top: list[dict] = []
    if payload.top_n and int(payload.top_n) > 0:
        cols = [
            c
            for c in [
                "txn_id",
                "sender_id",
                "receiver_id",
                "amount_usd",
                "sender_country",
                "receiver_country",
                "rule_score",
                "ml_score",
                "graph_score",
                "composite_risk_score",
                "risk_label",
                "is_sar_filed",
            ]
            if c in df_test.columns
        ]
        ranked = df_test.assign(_score=y_comp).sort_values("_score", ascending=False).head(int(payload.top_n))
        top = ranked[cols + ["_score"]].rename(columns={"_score": "composite_used_for_rank"}).to_dict("records")

    positives = int(y_true.sum())
    rows = int(len(df_test))
    prevalence = round(positives / max(rows, 1), 6)

    return {
        "split_strategy": split_strategy,
        "cutoff_timestamp": cutoff_ts,
        "train_rows": train_rows,
        "test_rows": test_rows,
        "rows": rows,
        "positives": positives,
        "prevalence": prevalence,
        "ml": ml_metrics,
        "composite": comp_metrics,
        "top": top,
        "notes": notes,
    }
