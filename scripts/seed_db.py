from __future__ import annotations

import argparse
import asyncio
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
    parser.add_argument("--reset", action="store_true", help="Drop and recreate tables before seeding (SQLite)")
    args = parser.parse_args()

    _add_src_to_path()

    if args.data_dir:
        os.environ["DATA_DIR"] = args.data_dir

    from app.utils.seed import seed_from_csv

    asyncio.run(seed_from_csv(reset=bool(args.reset)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
