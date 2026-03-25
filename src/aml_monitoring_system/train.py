"""
Model Training Script
---------------------
Trains two complementary models:
  1. XGBoostClassifier  — supervised binary classification (is_sar_filed)
  2. IsolationForest    — unsupervised anomaly detection

Usage:
    python -m app.ml.train --data data/transactions.csv --output app/ml/models/
"""
import argparse
import os
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.model_selection import train_test_split, StratifiedKFold
from sklearn.metrics import (
    classification_report, roc_auc_score, precision_recall_curve, average_precision_score
)
from sklearn.preprocessing import label_binarize
import xgboost as xgb
import structlog

from app.ml.features import build_training_features

logger = structlog.get_logger(__name__)


def train(data_path: str, output_dir: str, test_size: float = 0.2) -> None:
    os.makedirs(output_dir, exist_ok=True)

    logger.info("Loading training data", path=data_path)
    df = pd.read_csv(data_path)

    # ── Features & Labels ─────────────────────────────────────────────────────
    X = build_training_features(df)
    y_binary = df["is_sar_filed"].astype(int)

    logger.info("Dataset", total=len(df), positives=int(y_binary.sum()), features=len(X.columns))

    X_train, X_test, y_train, y_test = train_test_split(
        X, y_binary, test_size=test_size, random_state=42, stratify=y_binary
    )

    # ── XGBoost ───────────────────────────────────────────────────────────────
    pos_weight = (y_train == 0).sum() / max((y_train == 1).sum(), 1)
    xgb_model = xgb.XGBClassifier(
        n_estimators      = 300,
        max_depth         = 6,
        learning_rate     = 0.05,
        subsample         = 0.8,
        colsample_bytree  = 0.8,
        scale_pos_weight  = pos_weight,
        eval_metric       = "aucpr",
        random_state      = 42,
        use_label_encoder = False,
    )
    xgb_model.fit(
        X_train, y_train,
        eval_set=[(X_test, y_test)],
        verbose=False,
    )

    y_pred_proba = xgb_model.predict_proba(X_test)[:, 1]
    auc_roc = roc_auc_score(y_test, y_pred_proba)
    avg_prec = average_precision_score(y_test, y_pred_proba)
    logger.info("XGBoost evaluation", AUC_ROC=round(auc_roc, 4), Avg_Precision=round(avg_prec, 4))
    print(classification_report(y_test, (y_pred_proba > 0.5).astype(int)))

    xgb_path = os.path.join(output_dir, "xgb_aml_v1.joblib")
    joblib.dump(xgb_model, xgb_path)
    logger.info("XGBoost model saved", path=xgb_path)

    # ── Isolation Forest ──────────────────────────────────────────────────────
    # Train on ALL data (unsupervised)
    iso_model = IsolationForest(
        n_estimators  = 200,
        contamination = 0.05,   # expected ~5% anomaly rate
        random_state  = 42,
        n_jobs        = -1,
    )
    iso_model.fit(X)
    iso_path = os.path.join(output_dir, "isolation_forest_v1.joblib")
    joblib.dump(iso_model, iso_path)
    logger.info("Isolation Forest saved", path=iso_path)

    # ── Feature Importance ───────────────────────────────────────────────────
    fi = pd.DataFrame({
        "feature"   : X.columns,
        "importance": xgb_model.feature_importances_,
    }).sort_values("importance", ascending=False)
    logger.info("Top features", data=fi.head(5).to_dict("records"))
    fi.to_csv(os.path.join(output_dir, "feature_importance.csv"), index=False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data",   default="data/transactions.csv")
    parser.add_argument("--output", default="app/ml/models/")
    args = parser.parse_args()
    train(args.data, args.output)
