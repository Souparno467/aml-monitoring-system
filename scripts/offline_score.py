from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


def _add_src_to_path() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repo_root / "src"))


def _resolve_path(repo_root: Path, value: str) -> Path:
    p = Path(value)
    if p.is_absolute():
        return p
    return repo_root / p


def _load_xgb_model(models_dir: Path):
    try:
        import joblib  # type: ignore
    except Exception:
        return None

    model_path = models_dir / "xgb_aml_v1.joblib"
    if not model_path.exists():
        return None
    return joblib.load(model_path)


def _country_multiplier(level: str | None) -> float:
    level = (level or "").upper()
    if level == "CRITICAL":
        return 1.6
    if level == "HIGH":
        return 1.3
    if level == "MEDIUM":
        return 1.1
    return 1.0


def _risk_label(score: float, high: float, medium: float) -> str:
    if score >= 0.80:
        return "CRITICAL"
    if score >= high:
        return "HIGH"
    if score >= medium:
        return "MEDIUM"
    return "LOW"


def main() -> int:
    parser = argparse.ArgumentParser(description="Offline AML scoring on CSV datasets")
    parser.add_argument(
        "--transactions",
        default="src/aml_monitoring_system/data/transactions.csv",
        help="Path to transactions.csv",
    )
    parser.add_argument("--users", default="src/aml_monitoring_system/data/users.csv", help="Path to users.csv")
    parser.add_argument(
        "--pep",
        default="src/aml_monitoring_system/data/pep_registry.csv",
        help="Path to pep_registry.csv",
    )
    parser.add_argument(
        "--country-risk",
        default="src/aml_monitoring_system/data/country_risk.csv",
        help="Path to country_risk.csv",
    )
    parser.add_argument(
        "--graph-edges",
        default="src/aml_monitoring_system/data/graph_edges.csv",
        help="Optional: graph_edges.csv (for graph scoring)",
    )
    parser.add_argument(
        "--models-dir",
        default="src/app/ml/models",
        help="Directory containing joblib models (xgb_aml_v1.joblib)",
    )
    parser.add_argument("--out", default="", help="Optional output CSV path (scored transactions)")
    parser.add_argument("--top", type=int, default=20, help="Show top-N risky transactions")
    parser.add_argument("--evaluate", action="store_true", help="Compute basic accuracy metrics if labels exist")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    _add_src_to_path()
    from app.config import settings  # noqa: E402
    from app.services.aml_rules_engine import rules_engine  # noqa: E402

    try:
        import numpy as np  # type: ignore
        import pandas as pd  # type: ignore
    except Exception as exc:
        raise SystemExit("This script requires `pandas` and `numpy`. Install them, or run via Docker.") from exc

    tx_path = _resolve_path(repo_root, args.transactions)
    users_path = _resolve_path(repo_root, args.users)
    pep_path = _resolve_path(repo_root, args.pep)
    cr_path = _resolve_path(repo_root, args.country_risk)
    ge_path = _resolve_path(repo_root, args.graph_edges)
    models_dir = _resolve_path(repo_root, args.models_dir)

    if not tx_path.exists():
        raise SystemExit(f"transactions.csv not found: {tx_path}")

    df_tx = pd.read_csv(tx_path)
    df_users = pd.read_csv(users_path) if users_path.exists() else pd.DataFrame()

    df_tx["timestamp"] = pd.to_datetime(df_tx["timestamp"], utc=True, errors="coerce")
    df_tx = df_tx.dropna(subset=["timestamp"]).copy()

    # ---- PEP lookup (users.is_pep + pep_registry.csv)
    pep_user_ids: set[str] = set()
    if pep_path.exists():
        df_pep = pd.read_csv(pep_path)
        if "user_id" in df_pep.columns:
            pep_user_ids |= set(df_pep["user_id"].astype(str).str.strip())

    users_is_pep = {}
    if "user_id" in df_users.columns:
        is_pep_col = "is_pep" if "is_pep" in df_users.columns else None
        for row in df_users.to_dict("records"):
            uid = str(row.get("user_id", "")).strip()
            if not uid:
                continue
            flag = False
            if is_pep_col is not None:
                flag = bool(int(row.get(is_pep_col, 0) or 0))
            users_is_pep[uid] = flag

    # ---- Country risk levels
    country_level: dict[str, str] = {}
    if cr_path.exists():
        df_cr = pd.read_csv(cr_path)
        if "country_code" in df_cr.columns and "risk_level" in df_cr.columns:
            for row in df_cr.to_dict("records"):
                code = str(row.get("country_code", "")).strip().upper()
                level = str(row.get("risk_level", "")).strip().upper()
                if code:
                    country_level[code] = level

    # ---- Graph scores (optional)
    graph_score_by_user: dict[str, float] = {}
    if ge_path.exists():
        try:
            import networkx as nx  # type: ignore

            df_ge = pd.read_csv(ge_path)
            if {"source", "target"}.issubset(df_ge.columns):
                g = nx.DiGraph()
                for r in df_ge.to_dict("records"):
                    s = str(r.get("source", "")).strip()
                    t = str(r.get("target", "")).strip()
                    if not s or not t:
                        continue
                    w = float(r.get("weight", 1) or 1)
                    if g.has_edge(s, t):
                        g[s][t]["weight"] += w
                    else:
                        g.add_edge(s, t, weight=w)

                if g.number_of_nodes() > 0:
                    bc = nx.betweenness_centrality(g, k=min(300, g.number_of_nodes()), normalized=True, weight="weight")
                    pr = nx.pagerank(g, alpha=0.85, weight="weight")
                    for u in g.nodes():
                        bc_score = min(float(bc.get(u, 0.0)) * 10.0, 1.0)
                        pr_score = min(float(pr.get(u, 0.0)) * 1000.0, 1.0)
                        graph_score_by_user[u] = round(0.6 * bc_score + 0.4 * pr_score, 4)
        except Exception:
            graph_score_by_user = {}

    # ---- ML predictor (optional)
    xgb_model = _load_xgb_model(models_dir)
    xgb_features = getattr(xgb_model, "feature_names_in_", None) if xgb_model is not None else None

    # ---- Per-sender rolling context for structuring/velocity
    df_tx = df_tx.sort_values(["sender_id", "timestamp"]).reset_index(drop=True)
    recent_cnt = np.zeros(len(df_tx), dtype=np.int32)
    recent_total = np.zeros(len(df_tx), dtype=np.float64)

    window_seconds = int(settings.STRUCTURING_WINDOW_MINUTES) * 60

    for sender_id, idxs in df_tx.groupby("sender_id").groups.items():
        idxs_list = list(idxs)
        times = df_tx.loc[idxs_list, "timestamp"].astype("int64").to_numpy() // 10**9
        amounts = df_tx.loc[idxs_list, "amount_usd"].astype(float).to_numpy()

        left = 0
        running_sum = 0.0
        for i in range(len(idxs_list)):
            now = times[i]
            while left < i and (now - times[left]) > window_seconds:
                running_sum -= amounts[left]
                left += 1
            # window contains [left, i) previous txns within window
            recent_cnt[idxs_list[i]] = i - left
            recent_total[idxs_list[i]] = running_sum
            running_sum += amounts[i]

    # ---- Score each transaction
    out_rows: list[dict[str, Any]] = []
    for i, row in enumerate(df_tx.to_dict("records")):
        txn_id = str(row.get("txn_id"))
        sender_id = str(row.get("sender_id"))
        receiver_id = str(row.get("receiver_id"))

        sender_country = str(row.get("sender_country") or "").strip().upper()
        receiver_country = str(row.get("receiver_country") or "").strip().upper()

        is_pep_sender = bool(users_is_pep.get(sender_id, False) or (sender_id in pep_user_ids))
        is_pep_receiver = bool(users_is_pep.get(receiver_id, False) or (receiver_id in pep_user_ids))

        amount_usd = float(row.get("amount_usd") or 0.0)
        currency = str(row.get("currency") or "")
        payment_method = str(row.get("payment_method") or "")
        ts = row["timestamp"].to_pydatetime()

        dormant_days = 0
        # dormant_days exists on users.csv; join would be more expensive so do a tiny lookup:
        # keep it minimal (not required for scoring to work).

        rule_result = rules_engine.evaluate(
            txn_id=txn_id,
            amount_usd=amount_usd,
            currency=currency,
            payment_method=payment_method,
            sender_country=sender_country,
            receiver_country=receiver_country,
            timestamp=ts,
            is_pep_sender=is_pep_sender,
            is_pep_receiver=is_pep_receiver,
            dormant_days=dormant_days,
            recent_txn_count=int(recent_cnt[i]),
            recent_total_usd=float(recent_total[i]),
        )

        sender_level = country_level.get(sender_country)
        receiver_level = country_level.get(receiver_country)
        multiplier = max(_country_multiplier(sender_level), _country_multiplier(receiver_level))
        rule_score = round(min(rule_result.rule_score * multiplier, 1.0), 4)

        graph_score = float(graph_score_by_user.get(sender_id, 0.0))

        ml_score = 0.0
        if xgb_model is not None:
            features = {
                "amount_usd": amount_usd,
                "is_cross_border": int(row.get("is_cross_border") or 0),
                "hour_of_day": int(row.get("hour_of_day") or ts.hour),
                "is_pep_sender": int(is_pep_sender),
                "is_pep_receiver": int(is_pep_receiver),
                "recent_txn_count": int(recent_cnt[i]),
                "recent_total_usd": float(recent_total[i]),
                "dormant_days": dormant_days,
            }
            if xgb_features is None:
                X = pd.DataFrame([features])
            else:
                X = pd.DataFrame([[features.get(n, 0) for n in xgb_features]], columns=list(xgb_features))
            try:
                ml_score = float(xgb_model.predict_proba(X)[0][1])
            except Exception:
                ml_score = 0.0
        ml_score = max(0.0, min(ml_score, 1.0))

        composite = round(
            min(
                max(
                    rule_score * settings.RULE_SCORE_WEIGHT
                    + ml_score * settings.ML_SCORE_WEIGHT
                    + graph_score * settings.GRAPH_SCORE_WEIGHT,
                    0.0,
                ),
                1.0,
            ),
            4,
        )
        label = _risk_label(composite, settings.RISK_SCORE_HIGH_THRESHOLD, settings.RISK_SCORE_MEDIUM_THRESHOLD)

        out = dict(row)
        out["recent_txn_count"] = int(recent_cnt[i])
        out["recent_total_usd"] = float(round(recent_total[i], 4))
        out["rule_score_offline"] = rule_score
        out["ml_score_offline"] = round(ml_score, 4)
        out["graph_score_offline"] = round(graph_score, 4)
        out["composite_risk_score_offline"] = composite
        out["risk_label_offline"] = label
        out["triggered_rules_offline"] = json.dumps(rule_result.triggered_rules)
        out["flags_offline"] = json.dumps(rule_result.as_flags_dict())
        out_rows.append(out)

    df_out = pd.DataFrame(out_rows)

    # ---- Summary
    counts = Counter(df_out["risk_label_offline"].astype(str).tolist())
    print("Risk label distribution:", dict(counts))
    print()

    top_n = df_out.sort_values("composite_risk_score_offline", ascending=False).head(int(args.top))
    cols = [
        "txn_id",
        "sender_id",
        "receiver_id",
        "amount_usd",
        "sender_country",
        "receiver_country",
        "rule_score_offline",
        "ml_score_offline",
        "graph_score_offline",
        "composite_risk_score_offline",
        "risk_label_offline",
        "triggered_rules_offline",
    ]
    cols = [c for c in cols if c in top_n.columns]
    print(f"Top {int(args.top)} transactions by composite_risk_score_offline:")
    print(top_n[cols].to_string(index=False))
    print()

    # ---- Optional evaluation (if ground truth exists)
    if args.evaluate and "is_sar_filed" in df_out.columns:
        try:
            from sklearn.metrics import average_precision_score, roc_auc_score  # type: ignore

            y_true = df_out["is_sar_filed"].astype(int).to_numpy()
            y_ml = df_out["ml_score_offline"].astype(float).to_numpy()
            y_comp = df_out["composite_risk_score_offline"].astype(float).to_numpy()
            if y_true.sum() > 0 and y_true.sum() < len(y_true):
                print("Evaluation (binary label = is_sar_filed):")
                print("  ML ROC_AUC:", round(float(roc_auc_score(y_true, y_ml)), 4))
                print("  ML AvgPrecision:", round(float(average_precision_score(y_true, y_ml)), 4))
                print("  Composite ROC_AUC:", round(float(roc_auc_score(y_true, y_comp)), 4))
                print("  Composite AvgPrecision:", round(float(average_precision_score(y_true, y_comp)), 4))
                print()
            else:
                print("Evaluation skipped (label distribution unsuitable for AUC).")
        except Exception as exc:
            print("Evaluation skipped (missing sklearn):", str(exc))

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        df_out.to_csv(out_path, index=False)
        print("Wrote:", str(out_path))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())


