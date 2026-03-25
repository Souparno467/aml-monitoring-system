from __future__ import annotations

import pandas as pd


def build_training_features(df: "pd.DataFrame") -> "pd.DataFrame":
    cols = [
        "amount_usd",
        "is_cross_border",
        "hour_of_day",
        "flag_large_transaction",
        "flag_high_risk_country",
        "flag_pep_involved",
        "flag_structuring",
        "flag_dormant_account",
        "flag_crypto",
        "flag_night_transaction",
        "flag_round_amount",
        "recent_txn_count",
        "recent_total_usd",
    ]
    available = [c for c in cols if c in df.columns]
    return df[available].fillna(0)
