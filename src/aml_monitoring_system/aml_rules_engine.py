"""
AML Rules Engine
----------------
Evaluates a transaction against all configured AML rules and returns
a RuleEvaluationResult with per-rule flags and an aggregate rule_score.
"""
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional
import structlog

from app.config import settings

logger = structlog.get_logger(__name__)


@dataclass
class RuleEvaluationResult:
    txn_id                 : str
    flag_large_transaction : bool = False
    flag_high_risk_country : bool = False
    flag_pep_involved      : bool = False
    flag_structuring       : bool = False
    flag_dormant_account   : bool = False
    flag_crypto            : bool = False
    flag_night_transaction : bool = False
    flag_round_amount      : bool = False
    rule_score             : float = 0.0
    triggered_rules        : list[str] = field(default_factory=list)

    def as_flags_dict(self) -> dict:
        return {
            "large_transaction" : self.flag_large_transaction,
            "high_risk_country" : self.flag_high_risk_country,
            "pep_involved"      : self.flag_pep_involved,
            "structuring"       : self.flag_structuring,
            "dormant_account"   : self.flag_dormant_account,
            "crypto"            : self.flag_crypto,
            "night_transaction" : self.flag_night_transaction,
            "round_amount"      : self.flag_round_amount,
        }


# ── High-Risk Country List (FATF blacklist + greylist) ────────────────────────
HIGH_RISK_COUNTRIES = {
    "IR", "KP", "SY", "MM", "CU", "SD", "RU",
    "BY", "YE", "LY", "AF", "VE",
}

CRYPTO_CURRENCIES = {"BTC", "ETH", "XMR", "USDT", "BNB"}
CRYPTO_METHODS    = {"Crypto", "DeFi", "CEX"}

# Rule weights must sum to ≤ 1.0
RULE_WEIGHTS = {
    "LARGE_TXN"        : 0.15,
    "HIGH_RISK_COUNTRY": 0.25,
    "PEP_INVOLVED"     : 0.20,
    "STRUCTURING"      : 0.30,
    "DORMANT_ACCOUNT"  : 0.10,
    "CRYPTO"           : 0.15,
    "NIGHT_TXN"        : 0.05,
    "ROUND_AMOUNT"     : 0.05,
}


class AMLRulesEngine:
    """
    Stateless rules evaluator. Each rule is a pure function that receives
    transaction data and optional historical context.
    """

    def evaluate(
        self,
        txn_id            : str,
        amount_usd        : float,
        currency          : str,
        payment_method    : str,
        sender_country    : str,
        receiver_country  : str,
        timestamp         : datetime,
        is_pep_sender     : bool,
        is_pep_receiver   : bool,
        dormant_days      : int,
        recent_txn_count  : int,     # txns by sender in last STRUCTURING_WINDOW
        recent_total_usd  : float,   # total sent by sender in velocity window
    ) -> RuleEvaluationResult:

        result = RuleEvaluationResult(txn_id=txn_id)
        score  = 0.0

        # ── Rule 1: Large Transaction ──────────────────────────────────────────
        if amount_usd >= settings.LARGE_TXN_THRESHOLD_USD:
            result.flag_large_transaction = True
            result.triggered_rules.append("LARGE_TXN")
            score += RULE_WEIGHTS["LARGE_TXN"]

        # ── Rule 2: High-Risk Country ──────────────────────────────────────────
        if sender_country in HIGH_RISK_COUNTRIES or receiver_country in HIGH_RISK_COUNTRIES:
            result.flag_high_risk_country = True
            result.triggered_rules.append("HIGH_RISK_COUNTRY")
            score += RULE_WEIGHTS["HIGH_RISK_COUNTRY"]

        # ── Rule 3: PEP Involved ───────────────────────────────────────────────
        if is_pep_sender or is_pep_receiver:
            result.flag_pep_involved = True
            result.triggered_rules.append("PEP_INVOLVED")
            score += RULE_WEIGHTS["PEP_INVOLVED"]

        # ── Rule 4: Structuring / Smurfing ─────────────────────────────────────
        # Multiple sub-threshold transactions within window suggest deliberate
        # structuring to avoid reporting requirements (CTR threshold = $10k)
        is_just_under_threshold = 4_500 <= amount_usd < settings.LARGE_TXN_THRESHOLD_USD
        if is_just_under_threshold and recent_txn_count >= settings.STRUCTURING_COUNT_THRESHOLD:
            result.flag_structuring = True
            result.triggered_rules.append("STRUCTURING")
            score += RULE_WEIGHTS["STRUCTURING"]

        # ── Rule 5: Dormant Account Activation ────────────────────────────────
        if dormant_days >= 365 and amount_usd > 5_000:
            result.flag_dormant_account = True
            result.triggered_rules.append("DORMANT_ACCOUNT")
            score += RULE_WEIGHTS["DORMANT_ACCOUNT"]

        # ── Rule 6: Crypto / High-Anonymity ───────────────────────────────────
        if currency.upper() in CRYPTO_CURRENCIES or payment_method in CRYPTO_METHODS:
            result.flag_crypto = True
            result.triggered_rules.append("CRYPTO")
            score += RULE_WEIGHTS["CRYPTO"]

        # ── Rule 7: Night-time Transaction ────────────────────────────────────
        ts = timestamp if timestamp.tzinfo else timestamp.replace(tzinfo=timezone.utc)
        if ts.hour < 5 or ts.hour > 22:
            result.flag_night_transaction = True
            result.triggered_rules.append("NIGHT_TXN")
            score += RULE_WEIGHTS["NIGHT_TXN"]

        # ── Rule 8: Suspiciously Round Amount ─────────────────────────────────
        if amount_usd >= 5_000 and amount_usd % 1_000 == 0:
            result.flag_round_amount = True
            result.triggered_rules.append("ROUND_AMOUNT")
            score += RULE_WEIGHTS["ROUND_AMOUNT"]

        result.rule_score = round(min(score, 1.0), 4)

        logger.debug(
            "Rules evaluated",
            txn_id=txn_id,
            rules_triggered=result.triggered_rules,
            rule_score=result.rule_score,
        )
        return result


# Module-level singleton
rules_engine = AMLRulesEngine()
