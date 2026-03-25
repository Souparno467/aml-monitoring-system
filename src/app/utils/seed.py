from __future__ import annotations

import csv
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import insert, select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.session import _ensure_engine, init_db  # type: ignore
from app.models.alert import Alert
from app.core.audit import AuditLog
from app.models.country_risk import CountryRisk
from app.models.graph_edge import GraphEdge
from app.models.graph_node import GraphNode
from app.models.pep_profile import PEPProfile
from app.models.transaction import Transaction
from app.models.user import User
from app.services.graph_analysis import graph_service


_ALERT_RULE_MAP: dict[str, str] = {
    "NIGHT_TRANSACTION": "NIGHT_TXN",
    "DORMANT_ACTIVATION": "DORMANT_ACCOUNT",
    "CRYPTO_EXPOSURE": "CRYPTO",
}


def _normalize_alert_rule(value: Any) -> str | None:
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    key = raw.strip().upper()
    return _ALERT_RULE_MAP.get(key, raw)


def _normalize_alert_status(value: Any) -> str:
    raw = str(value or "Open").strip()
    return raw or "Open"


def _derive_alert_flags(status: str, sar_filed: bool, false_positive: bool) -> tuple[bool, bool]:
    s = (status or "").lower()
    if "sar" in s:
        sar_filed = True
    if "false" in s and "positive" in s:
        false_positive = True
    if sar_filed and false_positive:
        # prefer SAR filed over false positive
        false_positive = False
    return sar_filed, false_positive


def _recompute_resolution_hours(created_at: datetime | None, resolved_at: datetime | None) -> Decimal | None:
    if created_at is None or resolved_at is None:
        return None
    delta = resolved_at - created_at
    hours = max(delta.total_seconds() / 3600.0, 0.0)
    return Decimal(str(round(hours, 2)))


def _classify_label(score_0_1: Decimal | float) -> str:
    try:
        s = float(score_0_1)
    except Exception:
        s = 0.0
    if s >= 0.80:
        return "CRITICAL"
    if s >= settings.RISK_SCORE_HIGH_THRESHOLD:
        return "HIGH"
    if s >= settings.RISK_SCORE_MEDIUM_THRESHOLD:
        return "MEDIUM"
    return "LOW"


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    value = str(value).strip()
    if not value:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(value, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except Exception:
            continue
    try:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def _as_bool(v: Any) -> bool:
    if v is None:
        return False
    s = str(v).strip().lower()
    return s in {"1", "true", "t", "yes", "y"}


def _as_int(v: Any) -> int | None:
    if v is None or str(v).strip() == "":
        return None
    try:
        return int(float(v))
    except Exception:
        return None


def _as_float(v: Any) -> float | None:
    if v is None or str(v).strip() == "":
        return None
    try:
        return float(v)
    except Exception:
        return None


def _as_decimal(v: Any) -> Decimal | None:
    f = _as_float(v)
    if f is None:
        return None
    return Decimal(str(f))


def _read_csv(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _resolve_data_dir() -> Path:
    p = settings.resolve_path(settings.DATA_DIR)
    if p.exists():
        return p
    # fallback: repo_root/data
    repo_root = Path(__file__).resolve().parents[3]
    alt = repo_root / "data"
    return alt


async def get_db_counts(db: AsyncSession) -> dict[str, int]:
    users = (await db.execute(select(func.count()).select_from(User))).scalar_one()
    txns = (await db.execute(select(func.count()).select_from(Transaction))).scalar_one()
    alerts = (await db.execute(select(func.count()).select_from(Alert))).scalar_one()
    audit_logs = (await db.execute(select(func.count()).select_from(AuditLog))).scalar_one()
    return {"users": int(users), "transactions": int(txns), "alerts": int(alerts), "audit_logs": int(audit_logs)}


async def seed_from_csv(*, prime_graph: bool = True, reset: bool = False) -> dict[str, Any]:
    """Seed DB from CSVs in settings.DATA_DIR.

    Returns counts inserted from CSV row counts (not DB row counts).
    """

    await init_db()
    engine, SessionLocal = _ensure_engine()  # type: ignore

    if reset and settings.DATABASE_URL.startswith("sqlite"):
        from app.db.base import Base

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)

    # reset in-memory graph
    try:
        if getattr(graph_service, "_available", False) and getattr(graph_service, "_graph", None) is not None:
            graph_service._graph.clear()  # type: ignore[attr-defined]
    except Exception:
        pass

    data_dir = _resolve_data_dir()
    users_rows = _read_csv(data_dir / "users.csv")
    tx_rows = _read_csv(data_dir / "transactions.csv")
    alert_rows = _read_csv(data_dir / "alerts.csv")
    pep_rows = _read_csv(data_dir / "pep_registry.csv")
    cr_rows = _read_csv(data_dir / "country_risk.csv")
    gnodes_rows = _read_csv(data_dir / "graph_nodes.csv")
    gedges_rows = _read_csv(data_dir / "graph_edges.csv")

    async with SessionLocal() as session:
        async with session.begin():
            if cr_rows:
                values: list[dict[str, Any]] = []
                for r in cr_rows:
                    values.append(
                        {
                            "country_code": (r.get("country_code") or "").strip().upper(),
                            "risk_level": (r.get("risk_level") or "LOW").strip().upper(),
                            "risk_score_0_100": _as_decimal(r.get("risk_score_0_100")),
                            "fatf_greylist": _as_bool(r.get("fatf_greylist")),
                            "fatf_blacklist": _as_bool(r.get("fatf_blacklist")),
                            "ofac_sanctions": _as_bool(r.get("ofac_sanctions")),
                            "corruption_index": _as_decimal(r.get("corruption_index")),
                            "aml_deficiency_flag": _as_bool(r.get("aml_deficiency_flag")),
                            "last_updated": None,
                        }
                    )
                await session.execute(insert(CountryRisk).prefix_with("OR IGNORE"), values)

            if users_rows:
                values = []
                for r in users_rows:
                    uid = (r.get("user_id") or "").strip()
                    if not uid:
                        continue
                    values.append(
                        {
                            "user_id": uid,
                            "account_type": r.get("account_type") or "Individual",
                            "country": (r.get("country") or "").strip().upper()[:2],
                            "occupation": r.get("occupation"),
                            "risk_category": r.get("risk_category") or "LOW",
                            "kyc_verified": _as_bool(r.get("kyc_verified")),
                            "pep_flag": _as_bool(r.get("pep_flag")),
                            "sanctions_flag": _as_bool(r.get("sanctions_flag")),
                            "device_id": r.get("device_id"),
                            "account_created_at": _parse_dt(r.get("account_created_at")),
                            "last_login_at": _parse_dt(r.get("last_login_at")),
                            "dormant_days_before_activation": _as_int(r.get("dormant_days_before_activation")),
                            "account_status": r.get("account_status") or "Active",
                        }
                    )
                await session.execute(insert(User).prefix_with("OR IGNORE"), values)

            if pep_rows:
                values = []
                for r in pep_rows:
                    pid = (r.get("pep_id") or "").strip()
                    if not pid:
                        continue
                    values.append(
                        {
                            "pep_id": pid,
                            "user_id": (r.get("user_id") or "").strip() or None,
                            "role": r.get("role"),
                            "country": (r.get("country") or "").strip().upper()[:2] or None,
                            "designation_date": None,
                            "expiry_date": None,
                            "risk_weight_multiplier": _as_decimal(r.get("risk_weight_multiplier"))
                            or Decimal("1.5"),
                            "source": r.get("source"),
                            "last_verified": None,
                        }
                    )
                await session.execute(insert(PEPProfile).prefix_with("OR IGNORE"), values)

            if gnodes_rows:
                values = []
                for r in gnodes_rows:
                    uid = (r.get("user_id") or "").strip()
                    if not uid:
                        continue
                    values.append(
                        {
                            "user_id": uid,
                            "out_degree": _as_int(r.get("out_degree")) or 0,
                            "in_degree": _as_int(r.get("in_degree")) or 0,
                            "betweenness_centrality": _as_decimal(r.get("betweenness_centrality")),
                            "pagerank": _as_decimal(r.get("pagerank")),
                            "clustering_coefficient": _as_decimal(r.get("clustering_coefficient")),
                            "is_hub": _as_bool(r.get("is_hub")),
                        }
                    )
                await session.execute(insert(GraphNode).prefix_with("OR IGNORE"), values)

            if tx_rows:
                chunk: list[dict[str, Any]] = []
                for r in tx_rows:
                    tid = (r.get("txn_id") or "").strip()
                    if not tid:
                        continue
                    ts = _parse_dt(r.get("timestamp"))
                    if ts is None:
                        continue
                    chunk.append(
                        {
                            "txn_id": tid,
                            "sender_id": (r.get("sender_id") or "").strip(),
                            "receiver_id": (r.get("receiver_id") or "").strip(),
                            "amount_usd": _as_decimal(r.get("amount_usd")) or Decimal("0"),
                            "amount_local": _as_decimal(r.get("amount_local")) or Decimal("0"),
                            "currency": (r.get("currency") or "USD")[:3],
                            "fx_rate_to_usd": _as_decimal(r.get("fx_rate_to_usd")) or Decimal("1"),
                            "payment_method": r.get("payment_method"),
                            "txn_type": r.get("txn_type"),
                            "timestamp": ts,
                            "hour_of_day": _as_int(r.get("hour_of_day")) or ts.hour,
                            "day_of_week": r.get("day_of_week") or ts.strftime("%A"),
                            "is_weekend": _as_bool(r.get("is_weekend")),
                            "is_cross_border": _as_bool(r.get("is_cross_border")),
                            "sender_country": (r.get("sender_country") or "").strip().upper()[:2] or None,
                            "receiver_country": (r.get("receiver_country") or "").strip().upper()[:2] or None,
                            "transaction_fee_usd": _as_decimal(r.get("transaction_fee_usd")),
                            "flag_large_transaction": _as_bool(r.get("flag_large_transaction")),
                            "flag_high_risk_country": _as_bool(r.get("flag_high_risk_country")),
                            "flag_pep_involved": _as_bool(r.get("flag_pep_involved")),
                            "flag_structuring": _as_bool(r.get("flag_structuring")),
                            "flag_dormant_account": _as_bool(r.get("flag_dormant_account")),
                            "flag_crypto": _as_bool(r.get("flag_crypto")),
                            "flag_night_transaction": _as_bool(r.get("flag_night_transaction")),
                            "flag_round_amount": _as_bool(r.get("flag_round_amount")),
                            "rule_score": _as_decimal(r.get("rule_score")) or Decimal("0"),
                            "ml_score": _as_decimal(r.get("ml_score")) or Decimal("0"),
                            "graph_score": _as_decimal(r.get("graph_score")) or Decimal("0"),
                            "composite_risk_score": _as_decimal(r.get("composite_risk_score")) or Decimal("0"),
                            "risk_label": _classify_label(_as_decimal(r.get("composite_risk_score")) or Decimal("0")),
                            "pattern_type": r.get("pattern_type") or "normal",
                            "is_sar_filed": _as_bool(r.get("is_sar_filed")),
                            "status": r.get("status") or "Pending",
                            "device_fingerprint": r.get("device_fingerprint"),
                            "ip_country": r.get("ip_country"),
                            "channel": r.get("channel"),
                        }
                    )

                    if len(chunk) >= 2000:
                        await session.execute(insert(Transaction).prefix_with("OR IGNORE"), chunk)
                        chunk.clear()

                if chunk:
                    await session.execute(insert(Transaction).prefix_with("OR IGNORE"), chunk)

            if gedges_rows:
                values = []
                for r in gedges_rows:
                    s = (r.get("source") or "").strip()
                    t = (r.get("target") or "").strip()
                    if not s or not t:
                        continue
                    ts = _parse_dt(r.get("timestamp"))
                    values.append(
                        {
                            "source": s,
                            "target": t,
                            "txn_id": (r.get("txn_id") or "").strip() or None,
                            "weight": _as_decimal(r.get("weight")),
                            "composite_risk_score": _as_decimal(r.get("composite_risk_score")),
                            "timestamp": ts,
                        }
                    )
                    if prime_graph:
                        graph_service.add_transaction(
                            s,
                            t,
                            float(r.get("weight") or 0.0),
                            str(r.get("txn_id") or ""),
                        )
                if values:
                    await session.execute(insert(GraphEdge), values)

            if alert_rows:
                values = []
                for r in alert_rows:
                    aid = (r.get("alert_id") or "").strip()
                    if not aid:
                        continue
                    created_at = _parse_dt(r.get("alert_created_at"))
                    resolved_at = _parse_dt(r.get("alert_resolved_at"))

                    status = _normalize_alert_status(r.get("alert_status"))
                    sar_filed = _as_bool(r.get("sar_filed"))
                    false_positive = _as_bool(r.get("false_positive"))
                    sar_filed, false_positive = _derive_alert_flags(status, sar_filed, false_positive)

                    # Closed statuses should have resolved_at + resolution_time
                    if status.lower().startswith("closed"):
                        if created_at is not None and resolved_at is None:
                            resolved_at = created_at
                    else:
                        # Non-closed statuses should not be resolved
                        resolved_at = None

                    resolution_hours = _recompute_resolution_hours(created_at, resolved_at)

                    values.append(
                        {
                            "alert_id": aid,
                            "txn_id": (r.get("txn_id") or "").strip() or None,
                            "user_id": (r.get("user_id") or "").strip() or None,
                            "alert_rule": _normalize_alert_rule(r.get("alert_rule")),
                            "severity": (r.get("severity") or "MEDIUM").strip().upper(),
                            "composite_risk_score": _as_decimal(r.get("composite_risk_score")),
                            "rule_score": _as_decimal(r.get("rule_score")),
                            "ml_score": _as_decimal(r.get("ml_score")),
                            "graph_score": _as_decimal(r.get("graph_score")),
                            "alert_created_at": created_at,
                            "alert_resolved_at": resolved_at,
                            "resolution_time_hours": resolution_hours,
                            "assigned_analyst": r.get("assigned_analyst"),
                            "alert_status": status,
                            "sar_filed": sar_filed,
                            "false_positive": false_positive,
                            "notes": r.get("notes"),
                        }
                    )
                await session.execute(insert(Alert).prefix_with("OR IGNORE"), values)

        counts = await get_db_counts(session)

    return {
        "ok": True,
        "data_dir": str(data_dir),
        "rows_read": {
            "users": len(users_rows),
            "transactions": len(tx_rows),
            "alerts": len(alert_rows),
            "pep_profiles": len(pep_rows),
            "country_risk": len(cr_rows),
            "graph_nodes": len(gnodes_rows),
            "graph_edges": len(gedges_rows),
        },
        "db_counts": counts,
    }


async def ensure_seeded_if_empty() -> dict[str, Any] | None:
    if not settings.DEBUG or not settings.AUTO_SEED_DEMO:
        return None

    _, SessionLocal = _ensure_engine()  # type: ignore
    async with SessionLocal() as session:
        counts = await get_db_counts(session)
        if counts.get("transactions", 0) > 0:
            return None

    return await seed_from_csv()
