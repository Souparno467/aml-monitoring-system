from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.config import settings


@dataclass(frozen=True)
class TrainResult:
    model_path: Path
    rows: int
    positives: int
    prevalence: float
    roc_auc: float | None
    average_precision: float | None
    feature_columns: list[str]
    split_strategy: str
    cutoff_timestamp: str | None
    train_rows: int
    test_rows: int
    notes: list[str]


def _default_feature_columns(df_columns: list[str]) -> tuple[list[str], list[str]]:
    """Return (numeric_cols, categorical_cols) based on known dataset columns."""

    numeric = [
        "amount_usd",
        "transaction_fee_usd",
        "hour_of_day",
        "is_weekend",
        "is_cross_border",
        "flag_large_transaction",
        "flag_high_risk_country",
        "flag_pep_involved",
        "flag_structuring",
        "flag_dormant_account",
        "flag_crypto",
        "flag_night_transaction",
        "flag_round_amount",
        "graph_score",
    ]

    categorical = [
        "currency",
        "payment_method",
        "txn_type",
        "day_of_week",
        "sender_country",
        "receiver_country",
        "channel",
        "ip_country",
    ]

    numeric = [c for c in numeric if c in df_columns]
    categorical = [c for c in categorical if c in df_columns]
    return numeric, categorical


def train_xgb_from_csv(
    *,
    data_path: Path | None = None,
    model_dir: Path | None = None,
    max_rows: int | None = 200000,
    test_size: float = 0.2,
    random_state: int = 42,
    split_strategy: str = "time",
) -> TrainResult:
    if data_path is None:
        data_path = settings.resolve_path(settings.DATA_DIR) / "transactions.csv"
    if model_dir is None:
        model_dir = settings.resolve_path(settings.ML_MODEL_PATH)

    if not data_path.exists():
        raise FileNotFoundError(f"Dataset not found: {data_path}")

    model_dir.mkdir(parents=True, exist_ok=True)
    model_path = model_dir / "xgb_aml_v1.joblib"

    try:
        import pandas as pd  # type: ignore
    except Exception as exc:
        raise RuntimeError("pandas is required for training") from exc

    try:
        from sklearn.compose import ColumnTransformer  # type: ignore
        from sklearn.metrics import average_precision_score, roc_auc_score  # type: ignore
        from sklearn.model_selection import train_test_split  # type: ignore
        from sklearn.pipeline import Pipeline  # type: ignore
        from sklearn.preprocessing import OneHotEncoder  # type: ignore
    except Exception as exc:
        raise RuntimeError("scikit-learn is required for training") from exc

    try:
        from xgboost import XGBClassifier  # type: ignore
    except Exception as exc:
        raise RuntimeError("xgboost is required for training") from exc

    notes: list[str] = []

    df = pd.read_csv(data_path)
    if max_rows and len(df) > int(max_rows):
        df = df.sample(n=int(max_rows), random_state=random_state).copy()
        notes.append(f"Sampled max_rows={max_rows}")

    if "is_sar_filed" not in df.columns:
        raise ValueError("Dataset missing label column: is_sar_filed")

    y = df["is_sar_filed"].astype(int)

    numeric_cols, categorical_cols = _default_feature_columns(list(df.columns))
    feature_cols = numeric_cols + categorical_cols

    if not feature_cols:
        raise ValueError("No usable feature columns found in dataset")

    X = df[feature_cols].copy()

    for c in numeric_cols:
        X[c] = pd.to_numeric(X[c], errors="coerce").fillna(0)

    for c in categorical_cols:
        X[c] = X[c].astype(str).fillna("")

    # Split: prefer time-based holdout (older train, newer test) to avoid leakage.
    cutoff_ts = None
    strat = (split_strategy or "time").strip().lower()

    if strat == "time" and "timestamp" in df.columns:
        try:
            ts = pd.to_datetime(df["timestamp"], errors="coerce", utc=True)
            df = df.assign(_ts=ts).dropna(subset=["_ts"]).sort_values("_ts")
            X = df[feature_cols].copy()
            y = df["is_sar_filed"].astype(int)

            for c in numeric_cols:
                X[c] = pd.to_numeric(X[c], errors="coerce").fillna(0)
            for c in categorical_cols:
                X[c] = X[c].astype(str).fillna("")

            n = len(df)
            split_at = max(1, min(n - 1, int(round((1.0 - float(test_size)) * n))))
            X_train = X.iloc[:split_at].copy()
            y_train = y.iloc[:split_at].copy()
            X_test = X.iloc[split_at:].copy()
            y_test = y.iloc[split_at:].copy()

            cutoff_ts = df.iloc[split_at - 1]["_ts"].isoformat()
            notes.append(f"Time split: train older {split_at:,} / test newer {n - split_at:,}")
        except Exception:
            strat = "random"

    if strat != "time":
        X_train, X_test, y_train, y_test = train_test_split(
            X,
            y,
            test_size=float(test_size),
            random_state=random_state,
            stratify=y if y.nunique() > 1 else None,
        )
        notes.append("Random split")

    pos = int(y_train.sum())
    neg = int(len(y_train) - pos)
    scale_pos_weight = (neg / max(pos, 1)) if pos > 0 else 1.0

    pre = ColumnTransformer(
        transformers=[
            ("num", "passthrough", numeric_cols),
            (
                "cat",
                OneHotEncoder(handle_unknown="ignore", min_frequency=5),
                categorical_cols,
            ),
        ],
        remainder="drop",
    )

    clf = XGBClassifier(
        n_estimators=300,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.9,
        colsample_bytree=0.9,
        reg_lambda=1.0,
        min_child_weight=1,
        objective="binary:logistic",
        eval_metric="logloss",
        n_jobs=4,
        random_state=random_state,
        scale_pos_weight=scale_pos_weight,
    )

    pipe = Pipeline([("pre", pre), ("model", clf)])
    pipe.fit(X_train, y_train)

    y_prob = pipe.predict_proba(X_test)[:, 1]

    roc = float(roc_auc_score(y_test, y_prob)) if y_test.nunique() > 1 else None
    ap = float(average_precision_score(y_test, y_prob)) if y_test.nunique() > 1 else None

    try:
        import joblib  # type: ignore

        joblib.dump(pipe, model_path)
    except Exception as exc:
        raise RuntimeError(f"Failed saving model to {model_path}") from exc

    rows = int(len(df))
    positives = int(y.sum())
    prevalence = round(positives / max(rows, 1), 6)

    return TrainResult(
        model_path=model_path,
        rows=rows,
        positives=positives,
        prevalence=prevalence,
        roc_auc=roc,
        average_precision=ap,
        feature_columns=feature_cols,
        split_strategy=(split_strategy or "time"),
        cutoff_timestamp=cutoff_ts,
        train_rows=int(len(y_train)),
        test_rows=int(len(y_test)),
        notes=notes,
    )
