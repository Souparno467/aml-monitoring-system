from __future__ import annotations

from typing import Iterable


_RULE_REASON: dict[str, str] = {
    "LARGE_TXN": "Large transaction amount exceeding reporting threshold.",
    "VERY_LARGE_TXN": "Very large transaction amount (enhanced due diligence recommended).",
    "HIGH_RISK_COUNTRY": "Origin or destination involves a high-risk jurisdiction.",
    "PEP_INVOLVED": "PEP (politically exposed person) signal involved in the transaction.",
    "STRUCTURING": "Potential structuring: repeated transfers just under threshold within a short window.",
    "HIGH_FREQUENCY": "Unusually high recent transaction volume suggests rapid movement of funds.",
    "DORMANT_ACCOUNT": "Dormant account activity followed by a significant transaction.",
    "CRYPTO": "Crypto currency or payment rail involved (higher AML exposure).",
    "NIGHT_TXN": "Unusual time-of-day behavior (late night / early morning).",
    "ROUND_AMOUNT": "Round-number amount pattern (often seen in layering attempts).",
}


def explain_reasons(
    *,
    triggered_rules: Iterable[str] | None,
    is_cross_border: bool,
    ml_score: float,
    composite_score: float,
) -> list[str]:
    reasons: list[str] = []

    for code in list(triggered_rules or []):
        msg = _RULE_REASON.get(code)
        if msg:
            reasons.append(msg)

    if is_cross_border:
        reasons.append("Cross-border transfer increases AML risk due to jurisdictional complexity.")

    if ml_score >= 0.65:
        reasons.append("ML model indicates elevated risk based on patterns learned from historical data.")

    if not reasons:
        if composite_score >= 0.60:
            reasons.append("Composite risk score is elevated based on combined rules + model scoring.")
        else:
            reasons.append("No high-risk signals detected by rules; model score is within normal range.")

    deduped: list[str] = []
    seen: set[str] = set()
    for r in reasons:
        if r in seen:
            continue
        seen.add(r)
        deduped.append(r)

    return deduped
