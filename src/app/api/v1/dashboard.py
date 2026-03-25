from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import settings
from app.db.session import get_db
from app.models.transaction import Transaction
from app.utils.seed import get_db_counts, seed_from_csv
from app.utils.dataset_audit import audit_dataset

router = APIRouter()


@router.get("/ping")
async def ping():
    return {"ok": True}


@router.get("/status")
async def status(db: AsyncSession = Depends(get_db)):
    counts = await get_db_counts(db)
    return {
        "ok": True,
        "debug": settings.DEBUG,
        "auto_seed_demo": settings.AUTO_SEED_DEMO,
        "counts": counts,
    }


@router.get("/dataset-check")
async def dataset_check(max_rows: int = 200000):
    if not settings.DEBUG:
        raise HTTPException(status_code=404, detail="Not available")
    return audit_dataset(max_rows=max_rows)


@router.get("/db-check")
async def db_check(sample: int = 5000, db: AsyncSession = Depends(get_db)):
    if not settings.DEBUG:
        raise HTTPException(status_code=404, detail="Not available")

    sample = max(100, min(int(sample), 200000))

    res = await db.execute(
        select(
            Transaction.rule_score,
            Transaction.ml_score,
            Transaction.graph_score,
            Transaction.composite_risk_score,
            Transaction.risk_label,
        ).limit(sample)
    )
    rows = res.all()
    if not rows:
        return {"ok": True, "rows": 0, "note": "no transactions in DB"}

    def classify(score: float) -> str:
        if score >= 0.80:
            return "CRITICAL"
        if score >= settings.RISK_SCORE_HIGH_THRESHOLD:
            return "HIGH"
        if score >= settings.RISK_SCORE_MEDIUM_THRESHOLD:
            return "MEDIUM"
        return "LOW"

    errors = []
    mism = 0
    for r in rows:
        rule = float(r.rule_score or 0)
        ml = float(r.ml_score or 0)
        graph = float(r.graph_score or 0)
        comp = float(r.composite_risk_score or 0)
        calc = rule * settings.RULE_SCORE_WEIGHT + ml * settings.ML_SCORE_WEIGHT + graph * settings.GRAPH_SCORE_WEIGHT
        calc = max(0.0, min(calc, 1.0))
        errors.append(abs(calc - comp))
        if (r.risk_label or "").upper() != classify(comp):
            mism += 1

    errors.sort()
    mean_abs = sum(errors) / max(len(errors), 1)
    p95 = errors[int(0.95 * (len(errors) - 1))]

    return {
        "ok": True,
        "rows": len(rows),
        "weights_used": {
            "rule": float(settings.RULE_SCORE_WEIGHT),
            "ml": float(settings.ML_SCORE_WEIGHT),
            "graph": float(settings.GRAPH_SCORE_WEIGHT),
        },
        "composite_error": {
            "mean_abs": round(mean_abs, 6),
            "p95_abs": round(p95, 6),
            "max_abs": round(max(errors), 6),
        },
        "risk_label_mismatch": mism,
    }


@router.post("/seed")
async def seed_demo(reset: bool = False):
    """Seed the local DB from CSVs (portfolio/demo helper).

    Enabled only when DEBUG=true.
    """

    if not settings.DEBUG:
        raise HTTPException(status_code=404, detail="Not available")

    try:
        return await seed_from_csv(reset=bool(reset))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
