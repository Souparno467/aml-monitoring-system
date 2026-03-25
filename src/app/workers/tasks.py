from __future__ import annotations

import asyncio
from typing import Any

from app.workers.celery_worker import celery_app


if celery_app is not None:

    @celery_app.task(name="app.workers.tasks.ingest_transaction")
    def ingest_transaction(payload: dict[str, Any]) -> dict[str, Any]:
        """Ingest + score a transaction asynchronously (demo)."""

        async def _run() -> dict[str, Any]:
            from sqlalchemy import select
            from sqlalchemy.exc import IntegrityError

            from app.db.session import _ensure_engine, init_db
            from app.models.alert import Alert
            from app.models.transaction import Transaction
            from app.schemas.transaction_schema import TransactionCreate
            from app.services.transaction_service import transaction_service

            await init_db()
            _, SessionLocal = _ensure_engine()  # type: ignore

            async with SessionLocal() as db:
                data = TransactionCreate(**payload)

                try:
                    txn = await transaction_service.ingest(db, data)
                    await db.commit()
                    already_exists = False
                except IntegrityError:
                    # Common in demos: re-submitting the same txn_id. Make the async task idempotent.
                    await db.rollback()
                    txn = await db.get(Transaction, data.txn_id)
                    if txn is None:
                        raise
                    already_exists = True

                res = await db.execute(select(Alert).where(Alert.txn_id == txn.txn_id))
                alert = res.scalars().first()

                return {
                    "ok": True,
                    "txn_id": txn.txn_id,
                    "risk_label": txn.risk_label,
                    "composite_risk_score": float(txn.composite_risk_score or 0),
                    "alert_id": alert.alert_id if alert else None,
                    "already_exists": already_exists,
                }

        return asyncio.run(_run())


    @celery_app.task(name="app.workers.tasks.ping")
    def ping() -> dict[str, Any]:
        return {"ok": True}

else:
    # Celery not installed in this environment
    pass
