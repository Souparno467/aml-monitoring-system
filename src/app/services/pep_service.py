from __future__ import annotations

import csv
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.user import User


class PEPService:
    def __init__(self) -> None:
        self._loaded = False
        self._pep_user_ids: set[str] = set()

    def _load_registry(self) -> None:
        if self._loaded:
            return
        path = settings.resolve_path(settings.DATA_DIR) / "pep_registry.csv"
        if path.exists():
            with path.open("r", newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    uid = (row.get("user_id") or "").strip()
                    if uid:
                        self._pep_user_ids.add(uid)
        self._loaded = True

    async def check_and_tag(self, db: AsyncSession, user_id: str) -> dict:
        self._load_registry()
        user = await db.get(User, user_id)
        if user is None:
            return {"user_id": user_id, "is_pep": False}
        is_pep = bool(user.is_pep) or (user.user_id in self._pep_user_ids)
        if is_pep and not user.is_pep:
            user.is_pep = True
            await db.flush()
        return {"user_id": user_id, "is_pep": is_pep}


pep_service = PEPService()

