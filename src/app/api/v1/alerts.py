from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import AuditAction, audit
from app.db.session import get_db
from app.schemas.alert_schema import AlertListOut, AlertOut, AlertUpdate
from app.schemas.explain_schema import RiskExplainOut
from app.services.alert_service import alert_service
from app.services.explain_service import explain_alert
from app.models.transaction import Transaction

router = APIRouter()


@router.get("/", response_model=AlertListOut)
async def list_alerts(
    severity: str | None = None,
    user_id: str | None = None,
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    alerts, total = await alert_service.list(db, severity=severity, user_id=user_id, skip=skip, limit=limit)
    return {"total": total, "results": alerts}


@router.get("/{alert_id}", response_model=AlertOut)
async def get_alert(alert_id: str, db: AsyncSession = Depends(get_db)):
    return await alert_service.get_by_id(db, alert_id)




@router.get("/{alert_id}/explain", response_model=RiskExplainOut)
async def explain_one_alert(alert_id: str, db: AsyncSession = Depends(get_db)):
    alert = await alert_service.get_by_id(db, alert_id)
    txn = None
    if alert.txn_id:
        txn = await db.get(Transaction, alert.txn_id)
    return explain_alert(alert, txn)
@router.patch("/{alert_id}", response_model=AlertOut)
async def update_alert(
    alert_id: str,
    payload: AlertUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    old = (await alert_service.get_by_id(db, alert_id)).__dict__.copy()
    updated = await alert_service.update(
        db,
        alert_id,
        alert_status=payload.alert_status,
        notes=payload.notes,
        sar_filed=payload.sar_filed,
        false_positive=payload.false_positive,
    )

    action = AuditAction.ALERT_UPDATED
    if payload.sar_filed:
        action = AuditAction.SAR_FILED
    if payload.false_positive:
        action = AuditAction.FALSE_POSITIVE

    await audit.log(
        db,
        actor={"user_id": "portfolio", "role": "public"},
        action=action,
        entity_type="alert",
        entity_id=alert_id,
        old_value=old,
        new_value=updated.__dict__,
        request=request,
    )
    return updated


@router.post("/{alert_id}/escalate", response_model=AlertOut)
async def escalate_alert(
    alert_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    old = (await alert_service.get_by_id(db, alert_id)).__dict__.copy()
    updated = await alert_service.escalate(db, alert_id)
    await audit.log(
        db,
        actor={"user_id": "portfolio", "role": "public"},
        action=AuditAction.ALERT_ESCALATED,
        entity_type="alert",
        entity_id=alert_id,
        old_value=old,
        new_value=updated.__dict__,
        request=request,
    )
    return updated
