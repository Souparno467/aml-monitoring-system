from __future__ import annotations

import time
from datetime import timezone
from uuid import uuid4

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.logging import get_logger
from app.db.session import get_db
from app.ml.predict import ml_predictor
from app.models.transaction import Transaction
from app.schemas.explain_schema import RiskExplainOut
from app.schemas.transaction_schema import (
    TransactionCreate,
    TransactionListOut,
    TransactionOut,
    TransactionScoreIn,
    TransactionScoreOut,
)
from app.services.aml_rules_engine import rules_engine
from app.services.country_risk_service import country_risk_service
from app.services.risk_explain import explain_reasons
from app.services.transaction_service import transaction_service
from app.services.explain_service import explain_transaction
from app.workers.celery_worker import celery_app

router = APIRouter()
logger = get_logger(__name__)

_REDIS_CHECK_TTL_S = 5.0
_last_redis_check_at: float = 0.0
_last_redis_ok: bool | None = None


async def _redis_reachable() -> bool:
    """Fast preflight to avoid Celery's long Redis retry loop."""
    global _last_redis_check_at, _last_redis_ok

    now = time.monotonic()
    if _last_redis_ok is not None and (now - _last_redis_check_at) < _REDIS_CHECK_TTL_S:
        return _last_redis_ok

    ok = False
    try:
        import redis.asyncio as aioredis  # type: ignore

        r = aioredis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=1,
            socket_timeout=1,
        )
        await r.ping()
        try:
            await r.close()
        except Exception:
            pass
        ok = True
    except Exception:
        ok = False

    _last_redis_check_at = now
    _last_redis_ok = ok
    return ok


def _classify(score: float) -> str:
    if score >= 0.80:
        return "CRITICAL"
    if score >= settings.RISK_SCORE_HIGH_THRESHOLD:
        return "HIGH"
    if score >= settings.RISK_SCORE_MEDIUM_THRESHOLD:
        return "MEDIUM"
    return "LOW"


@router.get("/", response_model=TransactionListOut)
async def list_transactions(skip: int = 0, limit: int = 50, db: AsyncSession = Depends(get_db)):
    q = select(Transaction).order_by(Transaction.timestamp.desc())
    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar_one()
    txns = (await db.execute(q.offset(skip).limit(limit))).scalars().all()
    return {"total": int(total), "results": txns}


@router.get("/{txn_id}", response_model=TransactionOut)
async def get_transaction(txn_id: str, db: AsyncSession = Depends(get_db)):
    txn = await db.get(Transaction, txn_id)
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return txn




@router.get("/{txn_id}/explain", response_model=RiskExplainOut)
async def explain_txn(txn_id: str, db: AsyncSession = Depends(get_db)):
    txn = await db.get(Transaction, txn_id)
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return explain_transaction(txn)
@router.post("/", response_model=TransactionOut)
async def create_transaction(payload: TransactionCreate, db: AsyncSession = Depends(get_db)):
    return await transaction_service.ingest(db, payload)




@router.post("/async")
async def create_transaction_async(payload: TransactionCreate):
    """Queue transaction ingestion in Celery (demo)."""

    if celery_app is None:
        raise HTTPException(status_code=501, detail="Celery not available")

    if not await _redis_reachable():
        raise HTTPException(
            status_code=503,
            detail=(
                "Redis is not reachable for the async pipeline. "
                f"Check REDIS_URL ({settings.REDIS_URL}) and ensure Redis is running."
            ),
        )

    # Delay import so API can run without Celery worker.
    from app.workers.tasks import ingest_transaction  # type: ignore

    try:
        task = ingest_transaction.delay(payload.model_dump())  # type: ignore[attr-defined]
        return {"ok": True, "task_id": task.id}
    except Exception as e:
        logger.exception("celery_enqueue_failed", extra={"redis_url": settings.REDIS_URL})
        raise HTTPException(
            status_code=503,
            detail=(
                "Failed to enqueue Celery task (Redis/Celery unavailable). "
                f"Check Redis and restart the Celery worker. Cause: {type(e).__name__}"
            ),
        ) from e


@router.get("/tasks/{task_id}")
async def get_task(task_id: str):
    if celery_app is None:
        raise HTTPException(status_code=501, detail="Celery not available")

    if not await _redis_reachable():
        raise HTTPException(
            status_code=503,
            detail=(
                "Redis is not reachable for the async pipeline. "
                f"Check REDIS_URL ({settings.REDIS_URL}) and ensure Redis is running."
            ),
        )

    try:
        res = celery_app.AsyncResult(task_id)  # type: ignore[union-attr]
        out = {"task_id": task_id, "state": res.state}
        if res.successful():
            out["result"] = res.result
        elif res.failed():
            out["error"] = str(res.result)
        return out
    except Exception as e:
        logger.exception("celery_result_fetch_failed", extra={"redis_url": settings.REDIS_URL})
        raise HTTPException(
            status_code=503,
            detail=(
                "Failed to fetch Celery task status (Redis/Celery unavailable). "
                f"Check Redis and restart the Celery worker. Cause: {type(e).__name__}"
            ),
        ) from e
@router.post("/score", response_model=TransactionScoreOut)
async def score_transaction(payload: TransactionScoreIn = Body(default=TransactionScoreIn())):
    """Score an ad-hoc transaction (no IDs, no DB write) and return alert + explanation."""

    ts = payload.timestamp
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)

    txn_id = f"SIM-{uuid4().hex[:8].upper()}"

    sender_country = (payload.sender_country or "").strip().upper()[:2]
    receiver_country = (payload.receiver_country or "").strip().upper()[:2]
    ip_country = (payload.ip_country or "").strip().upper()[:2]

    data_warnings: list[str] = []

    is_cross_border_used = bool(payload.is_cross_border)
    if sender_country and receiver_country:
        derived = sender_country != receiver_country
        if derived != bool(payload.is_cross_border):
            data_warnings.append(
                "Cross-border flag contradicted sender/receiver countries; derived value was used instead."
            )
        is_cross_border_used = derived

    rule_eval = rules_engine.evaluate(
        txn_id=txn_id,
        amount_usd=float(payload.amount_usd),
        currency=str(payload.currency),
        payment_method=str(payload.payment_method or ""),
        sender_country=sender_country,
        receiver_country=receiver_country,
        timestamp=ts,
        is_pep_sender=bool(payload.pep_involved),
        is_pep_receiver=False,
        dormant_days=int(payload.dormant_days),
        recent_txn_count=int(payload.recent_txn_count),
        recent_total_usd=float(payload.recent_total_usd),
    )

    ml_features = {
        "amount_usd": float(payload.amount_usd),
        "hour_of_day": ts.hour,
        "is_weekend": int(ts.weekday() >= 5),
        "is_cross_border": int(is_cross_border_used),
        "graph_score": float(payload.graph_score),
        "currency": str(payload.currency),
        "payment_method": str(payload.payment_method or ""),
        "txn_type": str(payload.txn_type or ""),
        "day_of_week": ts.strftime("%A"),
        "sender_country": sender_country,
        "receiver_country": receiver_country,
        "channel": str(payload.channel or ""),
        "ip_country": ip_country,
        "flag_large_transaction": int(rule_eval.flag_large_transaction),
        "flag_high_risk_country": int(rule_eval.flag_high_risk_country),
        "flag_pep_involved": int(rule_eval.flag_pep_involved),
        "flag_structuring": int(rule_eval.flag_structuring),
        "flag_dormant_account": int(rule_eval.flag_dormant_account),
        "flag_crypto": int(rule_eval.flag_crypto),
        "flag_night_transaction": int(rule_eval.flag_night_transaction),
        "flag_round_amount": int(rule_eval.flag_round_amount),
    }

    ml_score = await ml_predictor.predict(ml_features)
    ml_model_loaded = getattr(ml_predictor, "_xgb", None) is not None

    multiplier = await country_risk_service.get_risk_multiplier(sender_country, receiver_country)
    adjusted_rule_score = round(min(float(rule_eval.rule_score) * float(multiplier), 1.0), 4)

    # If ML isn't available (model not loaded), redistribute ML weight to rules.
    rule_w = float(settings.RULE_SCORE_WEIGHT)
    ml_w = float(settings.ML_SCORE_WEIGHT)
    graph_w = float(settings.GRAPH_SCORE_WEIGHT)

    eff_rule_w = rule_w
    eff_ml_w = ml_w
    eff_graph_w = graph_w

    if not ml_model_loaded:
        eff_rule_w = rule_w + ml_w
        eff_ml_w = 0.0

    composite = (
        adjusted_rule_score * eff_rule_w
        + float(ml_score) * eff_ml_w
        + float(payload.graph_score) * eff_graph_w
    )
    composite = round(min(max(composite, 0.0), 1.0), 4)
    label = _classify(composite)

    alert_recommended = composite >= float(settings.RISK_SCORE_MEDIUM_THRESHOLD)
    severity = None
    if alert_recommended:
        severity = "MEDIUM"
        if composite >= 0.80:
            severity = "CRITICAL"
        elif composite >= float(settings.RISK_SCORE_HIGH_THRESHOLD):
            severity = "HIGH"

    reasons = explain_reasons(
        triggered_rules=list(rule_eval.triggered_rules or []),
        is_cross_border=bool(is_cross_border_used),
        ml_score=float(ml_score),
        composite_score=float(composite),
    )

    return {
        "composite_risk_score": float(composite),
        "risk_label": str(label),
        "severity": severity,
        "alert_recommended": bool(alert_recommended),
        "rule_score": float(adjusted_rule_score),
        "ml_score": float(round(float(ml_score), 4)),
        "graph_score": float(round(float(payload.graph_score), 4)),
        "ml_model_loaded": bool(ml_model_loaded),
        "is_cross_border_used": bool(is_cross_border_used),
        "data_warnings": data_warnings,
        "triggered_rules": list(rule_eval.triggered_rules or []),
        "reasons": reasons,
    }
