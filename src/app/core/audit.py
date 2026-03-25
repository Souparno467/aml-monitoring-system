from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Optional

from fastapi import Request
from sqlalchemy import JSON, Column, DateTime, String
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.base import Base

logger = get_logger(__name__)


class AuditAction:
    ALERT_VIEWED = "ALERT_VIEWED"
    ALERT_UPDATED = "ALERT_UPDATED"
    ALERT_ESCALATED = "ALERT_ESCALATED"
    SAR_FILED = "SAR_FILED"
    FALSE_POSITIVE = "FALSE_POSITIVE_MARKED"


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    actor_id = Column(String(60), nullable=False)
    actor_role = Column(String(20), nullable=False)
    action = Column(String(80), nullable=False)
    entity_type = Column(String(30), nullable=True)
    entity_id = Column(String(30), nullable=True)
    old_value = Column(JSON, nullable=True)
    new_value = Column(JSON, nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class AuditService:
    async def log(
        self,
        db: AsyncSession,
        actor: dict,
        action: str,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        old_value: Optional[Any] = None,
        new_value: Optional[Any] = None,
        request: Optional[Request] = None,
    ) -> Optional[AuditLog]:
        try:
            entry = AuditLog(
                actor_id=actor.get("user_id", "unknown"),
                actor_role=actor.get("role", "unknown"),
                action=action,
                entity_type=entity_type,
                entity_id=str(entity_id) if entity_id else None,
                old_value=_serialise(old_value),
                new_value=_serialise(new_value),
                ip_address=_get_ip(request),
                user_agent=_get_ua(request),
            )
            db.add(entry)
            await db.flush()
            return entry
        except Exception as exc:  # pragma: no cover
            logger.error("Audit log write failed", error=str(exc), action=action)
            return None


def _json_safe(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items() if k != "_sa_instance_state"}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(v) for v in value]
    return str(value)


def _serialise(value: Any) -> Optional[dict]:
    if value is None:
        return None
    if isinstance(value, dict):
        return _json_safe(value)
    if hasattr(value, "__dict__"):
        d = {k: v for k, v in value.__dict__.items() if not k.startswith("_") and k != "_sa_instance_state"}
        return _json_safe(d)
    return {"value": _json_safe(value)}


def _get_ip(request: Optional[Request]) -> Optional[str]:
    if not request:
        return None
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return getattr(request.client, "host", None)


def _get_ua(request: Optional[Request]) -> Optional[str]:
    if not request:
        return None
    return request.headers.get("User-Agent", "")[:255]


audit = AuditService()
