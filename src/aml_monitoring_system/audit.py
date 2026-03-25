"""
Audit Service
-------------
Writes an immutable trail to the audit_log table for every state-changing
action taken by an analyst or admin.

Usage (inside any route):
    from app.core.audit import audit
    await audit.log(db, actor=current_user, action="ALERT_UPDATED",
                    entity_type="alert", entity_id=alert_id,
                    old_value=old, new_value=new, request=request)
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import Request
from sqlalchemy import Column, String, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.db.base import Base

logger = structlog.get_logger(__name__)

# â”€â”€ Predefined action constants (use these instead of raw strings) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
class AuditAction:
    ALERT_VIEWED        = "ALERT_VIEWED"
    ALERT_UPDATED       = "ALERT_UPDATED"
    ALERT_ESCALATED     = "ALERT_ESCALATED"
    SAR_FILED           = "SAR_FILED"
    FALSE_POSITIVE      = "FALSE_POSITIVE_MARKED"
    TXN_BLOCKED         = "TRANSACTION_BLOCKED"
    TXN_REVIEWED        = "TRANSACTION_REVIEWED"
    USER_RISK_OVERRIDDEN= "USER_RISK_OVERRIDDEN"
    PEP_REGISTRY_RELOAD = "PEP_REGISTRY_RELOADED"
    COUNTRY_RISK_UPDATE = "COUNTRY_RISK_UPDATED"
    LOGIN               = "USER_LOGIN"
    GRAPH_REFRESH       = "GRAPH_REFRESH_TRIGGERED"


# â”€â”€ ORM Model â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
class AuditLog(Base):
    __tablename__ = "audit_log"

    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    actor_id    = Column(String(60),  nullable=False)
    actor_role  = Column(String(20),  nullable=False)
    action      = Column(String(80),  nullable=False)
    entity_type = Column(String(30),  nullable=True)
    entity_id   = Column(String(30),  nullable=True)
    old_value   = Column(JSONB,       nullable=True)
    new_value   = Column(JSONB,       nullable=True)
    ip_address  = Column(String(45),  nullable=True)
    user_agent  = Column(String(255), nullable=True)
    created_at  = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    def __repr__(self) -> str:
        return f"<AuditLog {self.action} by {self.actor_id} on {self.entity_type}:{self.entity_id}>"


# â”€â”€ Service â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
class AuditService:

    async def log(
        self,
        db          : AsyncSession,
        actor       : dict,                      # {"user_id": ..., "role": ...}
        action      : str,
        entity_type : Optional[str]  = None,
        entity_id   : Optional[str]  = None,
        old_value   : Optional[Any]  = None,
        new_value   : Optional[Any]  = None,
        request     : Optional[Request] = None,
    ) -> AuditLog:
        """
        Persist one audit entry. Never raises â€” logs error and continues
        so a failed audit write never blocks a user-facing operation.
        """
        try:
            entry = AuditLog(
                actor_id    = actor.get("user_id", "unknown"),
                actor_role  = actor.get("role", "unknown"),
                action      = action,
                entity_type = entity_type,
                entity_id   = str(entity_id) if entity_id else None,
                old_value   = _serialise(old_value),
                new_value   = _serialise(new_value),
                ip_address  = _get_ip(request),
                user_agent  = _get_ua(request),
            )
            db.add(entry)
            await db.flush()

            logger.info(
                "Audit entry written",
                actor=entry.actor_id,
                role=entry.actor_role,
                action=action,
                entity=f"{entity_type}:{entity_id}",
            )
            return entry

        except Exception as exc:
            # Audit failure must NEVER crash the main request
            logger.error("Audit log write failed", action=action, error=str(exc))
            return None

    async def get_history(
        self,
        db          : AsyncSession,
        entity_type : str,
        entity_id   : str,
        limit       : int = 50,
    ) -> list[AuditLog]:
        from sqlalchemy import select
        result = await db.execute(
            select(AuditLog)
            .where(
                AuditLog.entity_type == entity_type,
                AuditLog.entity_id   == str(entity_id),
            )
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
        )
        return result.scalars().all()

    async def get_actor_history(
        self,
        db      : AsyncSession,
        actor_id: str,
        limit   : int = 100,
    ) -> list[AuditLog]:
        from sqlalchemy import select
        result = await db.execute(
            select(AuditLog)
            .where(AuditLog.actor_id == actor_id)
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
        )
        return result.scalars().all()


# â”€â”€ Helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _serialise(value: Any) -> Optional[dict]:
    """Convert ORM objects / dataclasses / primitives to JSON-safe dict."""
    if value is None:
        return None
    if isinstance(value, dict):
        return value
    if hasattr(value, "__dict__"):
        return {
            k: str(v) for k, v in value.__dict__.items()
            if not k.startswith("_")
        }
    return {"value": str(value)}


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


# Module-level singleton
audit = AuditService()

