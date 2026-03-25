from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.alert import Alert


class AlertService:
    async def list(
        self,
        db: AsyncSession,
        *,
        severity: Optional[str] = None,
        user_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[Alert], int]:
        q = select(Alert)
        if severity:
            q = q.where(Alert.severity == severity.upper())
        if user_id:
            q = q.where(Alert.user_id == user_id)
        q = q.order_by(Alert.alert_created_at.desc())
        total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar_one()
        results = (await db.execute(q.offset(skip).limit(limit))).scalars().all()
        return results, int(total)

    async def get_by_id(self, db: AsyncSession, alert_id: str) -> Alert:
        alert = await db.get(Alert, alert_id)
        if not alert:
            raise HTTPException(status_code=404, detail="Alert not found")
        return alert

    async def update(
        self,
        db: AsyncSession,
        alert_id: str,
        *,
        alert_status: Optional[str] = None,
        notes: Optional[str] = None,
        sar_filed: Optional[bool] = None,
        false_positive: Optional[bool] = None,
    ) -> Alert:
        alert = await self.get_by_id(db, alert_id)

        if alert_status is not None:
            alert.alert_status = alert_status
        if notes is not None:
            alert.notes = notes
        if sar_filed is not None:
            alert.sar_filed = bool(sar_filed)
        if false_positive is not None:
            alert.false_positive = bool(false_positive)

        if (alert.alert_status or "").startswith("Closed"):
            if alert.alert_resolved_at is None:
                alert.alert_resolved_at = datetime.now(timezone.utc)
            if alert.alert_created_at:
                delta = alert.alert_resolved_at - alert.alert_created_at
                alert.resolution_time_hours = Decimal(str(round(delta.total_seconds() / 3600.0, 2)))

        alert.updated_at = datetime.now(timezone.utc)
        await db.flush()
        return alert

    async def escalate(self, db: AsyncSession, alert_id: str) -> Alert:
        alert = await self.get_by_id(db, alert_id)
        alert.alert_status = "Escalated"
        alert.updated_at = datetime.now(timezone.utc)
        await db.flush()
        return alert


alert_service = AlertService()
