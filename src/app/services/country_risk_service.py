from __future__ import annotations

import csv
from pathlib import Path

from app.config import settings


class CountryRiskService:
    def __init__(self) -> None:
        self._loaded = False
        self._risk_level: dict[str, str] = {}

    def _load(self) -> None:
        if self._loaded:
            return
        path = settings.resolve_path(settings.DATA_DIR) / "country_risk.csv"
        if path.exists():
            with path.open("r", newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    code = (row.get("country_code") or "").strip().upper()
                    level = (row.get("risk_level") or "").strip().upper()
                    if code:
                        self._risk_level[code] = level
        self._loaded = True

    async def get_risk_multiplier(self, sender_country: str, receiver_country: str) -> float:
        self._load()
        levels = {
            self._risk_level.get((sender_country or "").upper()),
            self._risk_level.get((receiver_country or "").upper()),
        }
        if "CRITICAL" in levels:
            return 1.6
        if "HIGH" in levels:
            return 1.3
        if "MEDIUM" in levels:
            return 1.1
        return 1.0


country_risk_service = CountryRiskService()

