from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional

from app.config import settings
from app.services.aml_rules_engine import rules_engine
from app.services.country_risk_service import country_risk_service

CACHE_TTL_SECONDS = 300


def _classify(score: float) -> str:
    if score >= 0.80:
        return "CRITICAL"
    if score >= settings.RISK_SCORE_HIGH_THRESHOLD:
        return "HIGH"
    if score >= settings.RISK_SCORE_MEDIUM_THRESHOLD:
        return "MEDIUM"
    return "LOW"


class RiskEngine:
    def __init__(self) -> None:
        self._redis = None
        self._redis_failed = False

    async def _get_redis(self):
        if self._redis_failed:
            return None
        if self._redis is not None:
            return self._redis

        try:
            import redis.asyncio as aioredis  # type: ignore

            r = aioredis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=1,
                socket_timeout=1,
            )
            await r.ping()
            self._redis = r
        except Exception:
            self._redis = None
            self._redis_failed = True

        return self._redis

    async def _get_cached(self, key: str) -> Optional[dict]:
        r = await self._get_redis()
        if r is None:
            return None
        try:
            raw = await r.get(key)
            return json.loads(raw) if raw else None
        except Exception:
            self._redis = None
            self._redis_failed = True
            return None

    async def _set_cached(self, key: str, data: dict) -> None:
        r = await self._get_redis()
        if r is None:
            return
        try:
            await r.setex(key, CACHE_TTL_SECONDS, json.dumps(data))
        except Exception:
            self._redis = None
            self._redis_failed = True
            return

    def _compute_composite(
        self,
        *,
        rule_score: float,
        ml_score: float,
        graph_score: float,
        ml_model_loaded: bool | None,
    ) -> tuple[float, str]:
        rule_w = float(settings.RULE_SCORE_WEIGHT)
        ml_w = float(settings.ML_SCORE_WEIGHT)
        graph_w = float(settings.GRAPH_SCORE_WEIGHT)

        # If ML isn't available, redistribute ML weight to rules.
        if ml_model_loaded is False:
            rule_w = rule_w + ml_w
            ml_w = 0.0

        composite = rule_score * rule_w + ml_score * ml_w + graph_score * graph_w
        composite = round(min(max(composite, 0.0), 1.0), 4)
        return composite, _classify(composite)

    async def score_transaction(
        self,
        *,
        txn_id: str,
        amount_usd: float,
        currency: str,
        payment_method: str,
        sender_country: str,
        receiver_country: str,
        timestamp: datetime,
        is_pep_sender: bool,
        is_pep_receiver: bool,
        dormant_days: int,
        recent_txn_count: int,
        recent_total_usd: float,
        ml_score: float,
        graph_score: float,
        ml_model_loaded: bool | None = None,
    ) -> dict:
        mode = "ml" if ml_model_loaded is not False else "no-ml"
        cache_key = f"risk:txn:{txn_id}:{mode}"
        cached = await self._get_cached(cache_key)
        if cached:
            return cached

        rule_result = rules_engine.evaluate(
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

        multiplier = await country_risk_service.get_risk_multiplier(sender_country, receiver_country)
        adjusted_rule_score = round(min(float(rule_result.rule_score) * float(multiplier), 1.0), 4)
        composite, label = self._compute_composite(
            rule_score=float(adjusted_rule_score),
            ml_score=float(ml_score),
            graph_score=float(graph_score),
            ml_model_loaded=ml_model_loaded,
        )

        result = {
            "txn_id": txn_id,
            "rule_score": adjusted_rule_score,
            "ml_score": round(float(ml_score), 4),
            "graph_score": round(float(graph_score), 4),
            "composite_risk_score": composite,
            "risk_label": label,
            "flags": rule_result.as_flags_dict(),
            "triggered_rules": rule_result.triggered_rules,
            "scored_at": datetime.now(timezone.utc).isoformat(),
        }
        await self._set_cached(cache_key, result)
        return result


risk_engine = RiskEngine()
