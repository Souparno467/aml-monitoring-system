"""
Risk Engine
-----------
Combines rule_score, ml_score, and graph_score into a final composite
risk score and persists it to the risk_scores table via Redis cache.

Formula:
  composite = (rule_score * 0.4) + (ml_score * 0.4) + (graph_score * 0.2)
"""
import json
from datetime import datetime, timezone
from typing import Optional
import redis.asyncio as aioredis
import structlog

from app.config import settings
from app.services.aml_rules_engine import rules_engine, RuleEvaluationResult
from app.services.country_risk_service import country_risk_service

logger = structlog.get_logger(__name__)

CACHE_TTL_SECONDS = 300   # 5 minutes


def _classify(score: float) -> str:
    if score >= 0.80:
        return "CRITICAL"
    if score >= settings.RISK_SCORE_HIGH_THRESHOLD:
        return "HIGH"
    if score >= settings.RISK_SCORE_MEDIUM_THRESHOLD:
        return "MEDIUM"
    return "LOW"


class RiskEngine:
    def __init__(self):
        self._redis: Optional[aioredis.Redis] = None

    async def _get_redis(self) -> aioredis.Redis:
        if self._redis is None:
            self._redis = await aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        return self._redis

    async def _get_cached(self, key: str) -> Optional[dict]:
        r = await self._get_redis()
        raw = await r.get(key)
        return json.loads(raw) if raw else None

    async def _set_cached(self, key: str, data: dict) -> None:
        r = await self._get_redis()
        await r.setex(key, CACHE_TTL_SECONDS, json.dumps(data))

    def compute_composite(
        self,
        rule_score  : float,
        ml_score    : float,
        graph_score : float,
    ) -> tuple[float, str]:
        """Return (composite_score, risk_label)."""
        composite = (
            rule_score  * settings.RULE_SCORE_WEIGHT +
            ml_score    * settings.ML_SCORE_WEIGHT   +
            graph_score * settings.GRAPH_SCORE_WEIGHT
        )
        composite = round(min(max(composite, 0.0), 1.0), 4)
        return composite, _classify(composite)

    async def score_transaction(
        self,
        txn_id          : str,
        amount_usd      : float,
        currency        : str,
        payment_method  : str,
        sender_country  : str,
        receiver_country: str,
        timestamp       : datetime,
        is_pep_sender   : bool,
        is_pep_receiver : bool,
        dormant_days    : int,
        recent_txn_count: int,
        recent_total_usd: float,
        ml_score        : float,
        graph_score     : float,
    ) -> dict:
        cache_key = f"risk:txn:{txn_id}"
        cached = await self._get_cached(cache_key)
        if cached:
            logger.debug("Risk score cache hit", txn_id=txn_id)
            return cached

        # Evaluate rules
        rule_result: RuleEvaluationResult = rules_engine.evaluate(
            txn_id=txn_id,
            amount_usd=amount_usd,
            currency=currency,
            payment_method=payment_method,
            sender_country=sender_country,
            receiver_country=receiver_country,
            timestamp=timestamp,
            is_pep_sender=is_pep_sender,
            is_pep_receiver=is_pep_receiver,
            dormant_days=dormant_days,
            recent_txn_count=recent_txn_count,
            recent_total_usd=recent_total_usd,
        )

        # Country risk multiplier
        country_multiplier = await country_risk_service.get_risk_multiplier(
            sender_country, receiver_country
        )
        adjusted_rule_score = round(min(rule_result.rule_score * country_multiplier, 1.0), 4)

        composite, risk_label = self.compute_composite(adjusted_rule_score, ml_score, graph_score)

        result = {
            "txn_id"              : txn_id,
            "rule_score"          : adjusted_rule_score,
            "ml_score"            : round(ml_score, 4),
            "graph_score"         : round(graph_score, 4),
            "composite_risk_score": composite,
            "risk_label"          : risk_label,
            "flags"               : rule_result.as_flags_dict(),
            "triggered_rules"     : rule_result.triggered_rules,
            "scored_at"           : datetime.now(timezone.utc).isoformat(),
        }

        await self._set_cached(cache_key, result)
        logger.info("Transaction scored", txn_id=txn_id, composite=composite, label=risk_label)
        return result

    async def score_user(self, user_id: str, txn_history_scores: list[float]) -> dict:
        """Aggregate risk score across a user's transaction history."""
        cache_key = f"risk:user:{user_id}"
        cached = await self._get_cached(cache_key)
        if cached:
            return cached

        if not txn_history_scores:
            final_score, risk_label = 0.0, "LOW"
        else:
            # Weight recent transactions more heavily
            weights = [1.0 + i * 0.1 for i in range(len(txn_history_scores))]
            weighted_sum = sum(s * w for s, w in zip(txn_history_scores, weights))
            final_score = round(min(weighted_sum / sum(weights), 1.0), 4)
            _, risk_label = self.compute_composite(final_score, final_score, 0)

        result = {
            "user_id"       : user_id,
            "final_score"   : final_score,
            "risk_label"    : risk_label,
            "txn_count"     : len(txn_history_scores),
            "scored_at"     : datetime.now(timezone.utc).isoformat(),
        }
        await self._set_cached(cache_key, result)
        return result


risk_engine = RiskEngine()
