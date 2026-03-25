"""
Transaction Service
-------------------
Orchestrates the full transaction ingestion pipeline:
  1. Persist raw transaction
  2. Pull historical context for rules
  3. Get ML prediction
  4. Get graph score
  5. Run rules engine
  6. Compute composite risk score
  7. Generate alert if above threshold
  8. Return enriched transaction
"""
from datetime import datetime, timedelta, timezone
from typing import Optional
import structlog
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.transaction import Transaction
from app.models.user import User
from app.models.alert import Alert
from app.schemas.transaction_schema import TransactionCreate
from app.services.risk_engine import risk_engine
from app.services.pep_service import pep_service
from app.ml.predict import ml_predictor
from app.services.graph_analysis import graph_service
from app.config import settings

logger = structlog.get_logger(__name__)


class TransactionService:

    async def ingest(self, db: AsyncSession, data: TransactionCreate) -> Transaction:
        """Full ingestion pipeline for a new transaction."""

        # ── 1. Fetch sender/receiver context ──────────────────────────────────
        sender   = await db.get(User, data.sender_id)
        receiver = await db.get(User, data.receiver_id)

        # ── 2. Historical context for structuring / velocity checks ───────────
        window_start = data.timestamp - timedelta(minutes=settings.STRUCTURING_WINDOW_MINUTES)
        recent_result = await db.execute(
            select(
                func.count(Transaction.txn_id).label("cnt"),
                func.coalesce(func.sum(Transaction.amount_usd), 0).label("total"),
            ).where(
                Transaction.sender_id == data.sender_id,
                Transaction.timestamp >= window_start,
            )
        )
        row = recent_result.one()
        recent_txn_count = int(row.cnt)
        recent_total_usd = float(row.total)

        # ── 3. PEP check ──────────────────────────────────────────────────────
        pep_sender   = await pep_service.check_and_tag(db, data.sender_id)
        pep_receiver = await pep_service.check_and_tag(db, data.receiver_id)

        # ── 4. ML score ───────────────────────────────────────────────────────
        ml_features = {
            "amount_usd"       : data.amount_usd,
            "is_cross_border"  : int(data.is_cross_border),
            "hour_of_day"      : data.timestamp.hour,
            "is_pep_sender"    : int(pep_sender["is_pep"]),
            "is_pep_receiver"  : int(pep_receiver["is_pep"]),
            "recent_txn_count" : recent_txn_count,
            "recent_total_usd" : recent_total_usd,
            "dormant_days"     : sender.dormant_days_before_activation if sender else 0,
        }
        ml_score = await ml_predictor.predict(ml_features)

        # ── 5. Graph score ────────────────────────────────────────────────────
        graph_score = graph_service.compute_graph_score(data.sender_id)

        # ── 6. Risk scoring ───────────────────────────────────────────────────
        risk_result = await risk_engine.score_transaction(
            txn_id           = data.txn_id,
            amount_usd       = data.amount_usd,
            currency         = data.currency,
            payment_method   = data.payment_method or "",
            sender_country   = data.sender_country or (sender.country if sender else "US"),
            receiver_country = data.receiver_country or (receiver.country if receiver else "US"),
            timestamp        = data.timestamp,
            is_pep_sender    = pep_sender["is_pep"],
            is_pep_receiver  = pep_receiver["is_pep"],
            dormant_days     = sender.dormant_days_before_activation if sender else 0,
            recent_txn_count = recent_txn_count,
            recent_total_usd = recent_total_usd,
            ml_score         = ml_score,
            graph_score      = graph_score,
        )

        # ── 7. Build ORM object ───────────────────────────────────────────────
        flags = risk_result["flags"]
        txn = Transaction(
            txn_id                 = data.txn_id,
            sender_id              = data.sender_id,
            receiver_id            = data.receiver_id,
            amount_usd             = data.amount_usd,
            amount_local           = data.amount_local,
            currency               = data.currency,
            fx_rate_to_usd         = data.fx_rate_to_usd,
            payment_method         = data.payment_method,
            txn_type               = data.txn_type,
            timestamp              = data.timestamp,
            hour_of_day            = data.timestamp.hour,
            day_of_week            = data.timestamp.strftime("%A"),
            is_weekend             = data.timestamp.weekday() >= 5,
            is_cross_border        = data.is_cross_border,
            sender_country         = data.sender_country,
            receiver_country       = data.receiver_country,
            device_fingerprint     = data.device_fingerprint,
            ip_country             = data.ip_country,
            channel                = data.channel,
            flag_large_transaction = flags["large_transaction"],
            flag_high_risk_country = flags["high_risk_country"],
            flag_pep_involved      = flags["pep_involved"],
            flag_structuring       = flags["structuring"],
            flag_dormant_account   = flags["dormant_account"],
            flag_crypto            = flags["crypto"],
            flag_night_transaction = flags["night_transaction"],
            flag_round_amount      = flags["round_amount"],
            rule_score             = risk_result["rule_score"],
            ml_score               = risk_result["ml_score"],
            graph_score            = risk_result["graph_score"],
            composite_risk_score   = risk_result["composite_risk_score"],
            risk_label             = risk_result["risk_label"],
            status                 = "Pending",
        )
        db.add(txn)

        # ── 8. Auto-generate alert if above threshold ─────────────────────────
        if risk_result["composite_risk_score"] >= settings.RISK_SCORE_MEDIUM_THRESHOLD:
            await self._generate_alert(db, txn, risk_result)

        await db.flush()
        logger.info(
            "Transaction ingested",
            txn_id=data.txn_id,
            risk=risk_result["composite_risk_score"],
            label=risk_result["risk_label"],
        )
        return txn

    async def _generate_alert(self, db: AsyncSession, txn: Transaction, risk_result: dict) -> None:
        composite = risk_result["composite_risk_score"]
        if composite >= 0.80:
            severity = "CRITICAL"
        elif composite >= settings.RISK_SCORE_HIGH_THRESHOLD:
            severity = "HIGH"
        else:
            severity = "MEDIUM"

        primary_rule = risk_result["triggered_rules"][0] if risk_result["triggered_rules"] else "COMPOSITE_SCORE"

        alert = Alert(
            alert_id             = f"ALT-{txn.txn_id}",
            txn_id               = txn.txn_id,
            user_id              = txn.sender_id,
            alert_rule           = primary_rule,
            severity             = severity,
            composite_risk_score = composite,
            rule_score           = risk_result["rule_score"],
            ml_score             = risk_result["ml_score"],
            graph_score          = risk_result["graph_score"],
            alert_status         = "Open",
        )
        db.add(alert)
        logger.info("Alert generated", alert_id=alert.alert_id, severity=severity, txn_id=txn.txn_id)

    async def get_by_id(self, db: AsyncSession, txn_id: str) -> Optional[Transaction]:
        return await db.get(Transaction, txn_id)

    async def list_transactions(
        self,
        db         : AsyncSession,
        risk_label : Optional[str] = None,
        sender_id  : Optional[str] = None,
        skip       : int = 0,
        limit      : int = 50,
    ) -> tuple[list[Transaction], int]:
        q = select(Transaction)
        if risk_label:
            q = q.where(Transaction.risk_label == risk_label.upper())
        if sender_id:
            q = q.where(Transaction.sender_id == sender_id)
        q = q.order_by(Transaction.timestamp.desc())

        total_q  = select(func.count()).select_from(q.subquery())
        total    = (await db.execute(total_q)).scalar_one()
        result   = await db.execute(q.offset(skip).limit(limit))
        txns     = result.scalars().all()
        return txns, total


transaction_service = TransactionService()
