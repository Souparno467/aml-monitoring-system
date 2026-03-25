from __future__ import annotations

from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.ml.predict import ml_predictor
from app.models.alert import Alert
from app.models.graph_node import GraphNode
from app.models.transaction import Transaction
from app.models.user import User
from app.schemas.transaction_schema import TransactionCreate
from app.services.aml_rules_engine import rules_engine
from app.services.pep_service import pep_service
from app.services.risk_engine import risk_engine


class TransactionService:
    @staticmethod
    def _graph_score_from_node(node: GraphNode | None) -> float:
        """Compute graph_score using precomputed node metrics.

        Avoids on-request centrality computation.
        """

        if not node:
            return 0.0

        bc = float(node.betweenness_centrality or 0)
        pr = float(node.pagerank or 0)

        bc_score = min(bc * 10.0, 1.0)
        pr_score = min(pr * 1000.0, 1.0)
        base = 0.6 * bc_score + 0.4 * pr_score

        if base <= 0.0:
            deg = float(node.total_degree)
            base = min(deg / 40.0, 1.0) * 0.25

        return round(min(max(base, 0.0), 1.0), 4)

    async def ingest(self, db: AsyncSession, data: TransactionCreate) -> Transaction:
        sender = await db.get(User, data.sender_id)
        receiver = await db.get(User, data.receiver_id)

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

        pep_sender = await pep_service.check_and_tag(db, data.sender_id)
        pep_receiver = await pep_service.check_and_tag(db, data.receiver_id)

        sender_country = (data.sender_country or (sender.country if sender else "") or "").strip().upper()[:2]
        receiver_country = (data.receiver_country or (receiver.country if receiver else "") or "").strip().upper()[:2]

        is_cross_border = bool(data.is_cross_border)
        if sender_country and receiver_country:
            is_cross_border = sender_country != receiver_country

        dormant_days = int(getattr(sender, "dormant_days_before_activation", 0) or 0)

        # Use precomputed node metrics (seeded / batch-computed) instead of
        # computing centrality on every ingest request.
        sender_node = await db.get(GraphNode, data.sender_id)
        receiver_node = await db.get(GraphNode, data.receiver_id)
        if sender_node is None:
            sender_node = GraphNode(user_id=data.sender_id, out_degree=0, in_degree=0)
            db.add(sender_node)
        if receiver_node is None:
            receiver_node = GraphNode(user_id=data.receiver_id, out_degree=0, in_degree=0)
            db.add(receiver_node)
        sender_node.out_degree = int(sender_node.out_degree or 0) + 1
        receiver_node.in_degree = int(receiver_node.in_degree or 0) + 1

        graph_score = self._graph_score_from_node(sender_node)
        rule_eval = rules_engine.evaluate(
            txn_id=data.txn_id,
            amount_usd=data.amount_usd,
            currency=data.currency,
            payment_method=data.payment_method or "",
            sender_country=sender_country,
            receiver_country=receiver_country,
            timestamp=data.timestamp,
            is_pep_sender=bool(pep_sender["is_pep"]),
            is_pep_receiver=bool(pep_receiver["is_pep"]),
            dormant_days=dormant_days,
            recent_txn_count=recent_txn_count,
            recent_total_usd=recent_total_usd,
        )

        ml_features = {
            "amount_usd": data.amount_usd,
            "hour_of_day": data.timestamp.hour,
            "is_weekend": int(data.timestamp.weekday() >= 5),
            "is_cross_border": int(is_cross_border),
            "graph_score": graph_score,
            "currency": data.currency,
            "payment_method": data.payment_method or "",
            "txn_type": data.txn_type or "",
            "day_of_week": data.timestamp.strftime("%A"),
            "sender_country": sender_country,
            "receiver_country": receiver_country,
            "channel": data.channel or "",
            "ip_country": (data.ip_country or ""),
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

        risk_result = await risk_engine.score_transaction(
            txn_id=data.txn_id,
            amount_usd=data.amount_usd,
            currency=data.currency,
            payment_method=data.payment_method or "",
            sender_country=sender_country,
            receiver_country=receiver_country,
            timestamp=data.timestamp,
            is_pep_sender=bool(pep_sender["is_pep"]),
            is_pep_receiver=bool(pep_receiver["is_pep"]),
            dormant_days=dormant_days,
            recent_txn_count=recent_txn_count,
            recent_total_usd=recent_total_usd,
            ml_score=ml_score,
            graph_score=graph_score,
            ml_model_loaded=ml_model_loaded,
        )

        flags = risk_result["flags"]
        txn = Transaction(
            txn_id=data.txn_id,
            sender_id=data.sender_id,
            receiver_id=data.receiver_id,
            amount_usd=data.amount_usd,
            amount_local=data.amount_local,
            currency=data.currency,
            fx_rate_to_usd=data.fx_rate_to_usd,
            payment_method=data.payment_method,
            txn_type=data.txn_type,
            timestamp=data.timestamp,
            hour_of_day=data.timestamp.hour,
            day_of_week=data.timestamp.strftime("%A"),
            is_weekend=data.timestamp.weekday() >= 5,
            is_cross_border=is_cross_border,
            sender_country=sender_country or None,
            receiver_country=receiver_country or None,
            device_fingerprint=data.device_fingerprint,
            ip_country=data.ip_country,
            channel=data.channel,
            flag_large_transaction=flags.get("large_transaction"),
            flag_high_risk_country=flags.get("high_risk_country"),
            flag_pep_involved=flags.get("pep_involved"),
            flag_structuring=flags.get("structuring"),
            flag_dormant_account=flags.get("dormant_account"),
            flag_crypto=flags.get("crypto"),
            flag_night_transaction=flags.get("night_transaction"),
            flag_round_amount=flags.get("round_amount"),
            rule_score=risk_result["rule_score"],
            ml_score=risk_result["ml_score"],
            graph_score=risk_result["graph_score"],
            composite_risk_score=risk_result["composite_risk_score"],
            risk_label=risk_result["risk_label"],
            status="Pending",
        )
        db.add(txn)

        if float(risk_result["composite_risk_score"]) >= settings.RISK_SCORE_MEDIUM_THRESHOLD:
            primary_rule = risk_result["triggered_rules"][0] if risk_result["triggered_rules"] else "COMPOSITE_SCORE"
            severity = "MEDIUM"
            if float(risk_result["composite_risk_score"]) >= 0.80:
                severity = "CRITICAL"
            elif float(risk_result["composite_risk_score"]) >= settings.RISK_SCORE_HIGH_THRESHOLD:
                severity = "HIGH"

            alert = Alert(
                alert_id=f"ALT-{data.txn_id}",
                txn_id=data.txn_id,
                user_id=data.sender_id,
                alert_rule=primary_rule,
                severity=severity,
                composite_risk_score=risk_result["composite_risk_score"],
                rule_score=risk_result["rule_score"],
                ml_score=risk_result["ml_score"],
                graph_score=risk_result["graph_score"],
                alert_status="Open",
            )
            db.add(alert)

        await db.flush()
        return txn


transaction_service = TransactionService()
