from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def _add_src_to_path() -> Path:
    repo_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repo_root / "src"))
    return repo_root


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default="", help="Override DATA_DIR")
    parser.add_argument("--max-rows", type=int, default=200000)
    parser.add_argument("--test-size", type=float, default=0.2)
    args = parser.parse_args()

    _add_src_to_path()

    if args.data_dir:
        os.environ["DATA_DIR"] = args.data_dir

    from app.ml.train import train_xgb_from_csv

    res = train_xgb_from_csv(max_rows=args.max_rows, test_size=args.test_size)

    print("Trained XGBoost model")
    print("  model_path:", res.model_path)
    print("  rows:", res.rows)
    print("  positives:", res.positives)
    print("  prevalence:", res.prevalence)
    print("  roc_auc:", res.roc_auc)
    print("  average_precision:", res.average_precision)
    print("  features:", len(res.feature_columns))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
