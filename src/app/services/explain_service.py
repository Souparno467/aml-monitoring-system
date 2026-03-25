from __future__ import annotations

from typing import Optional

from app.config import settings
from app.models.alert import Alert
from app.models.transaction import Transaction
from app.services.risk_explain import explain_reasons


def _flags_to_rules(txn: Transaction) -> list[str]:
    rules: list[str] = []
    if getattr(txn, "flag_large_transaction", False):
        rules.append("LARGE_TXN")
    if getattr(txn, "flag_high_risk_country", False):
        rules.append("HIGH_RISK_COUNTRY")
    if getattr(txn, "flag_pep_involved", False):
        rules.append("PEP_INVOLVED")
    if getattr(txn, "flag_structuring", False):
        rules.append("STRUCTURING")
    if getattr(txn, "flag_dormant_account", False):
        rules.append("DORMANT_ACCOUNT")
    if getattr(txn, "flag_crypto", False):
        rules.append("CRYPTO")
    if getattr(txn, "flag_night_transaction", False):
        rules.append("NIGHT_TXN")
    if getattr(txn, "flag_round_amount", False):
        rules.append("ROUND_AMOUNT")
    return rules


def _breakdown(rule_score: float, ml_score: float, graph_score: float) -> dict:
    rw = float(settings.RULE_SCORE_WEIGHT)
    mw = float(settings.ML_SCORE_WEIGHT)
    gw = float(settings.GRAPH_SCORE_WEIGHT)
    return {
        "rule": {
            "score": float(rule_score),
            "weight": rw,
            "contribution": round(float(rule_score) * rw, 4),
        },
        "ml": {
            "score": float(ml_score),
            "weight": mw,
            "contribution": round(float(ml_score) * mw, 4),
        },
        "graph": {
            "score": float(graph_score),
            "weight": gw,
            "contribution": round(float(graph_score) * gw, 4),
        },
    }


def _highlights_from_txn(txn: Transaction) -> list[dict]:
    sender_country = (getattr(txn, "sender_country", "") or "").upper()
    receiver_country = (getattr(txn, "receiver_country", "") or "").upper()
    highlights: list[dict] = []

    highlights.append(
        {
            "label": "Amount (USD)",
            "value": f"{float(txn.amount_usd):,.2f}",
            "why": "Higher amounts can increase risk." if float(txn.amount_usd) >= 10000 else None,
        }
    )
    if sender_country or receiver_country:
        highlights.append(
            {
                "label": "Route",
                "value": f"{sender_country or '??'} → {receiver_country or '??'}",
                "why": "Cross-border activity often increases AML risk." if sender_country and receiver_country and sender_country != receiver_country else None,
            }
        )

    pm = getattr(txn, "payment_method", None)
    if pm:
        highlights.append(
            {
                "label": "Payment Method",
                "value": str(pm),
                "why": "Crypto rails typically carry higher AML exposure." if str(pm).lower() in {"crypto", "defi", "cex"} else None,
            }
        )

    ts = getattr(txn, "timestamp", None)
    if ts is not None:
        highlights.append(
            {
                "label": "Time (UTC)",
                "value": ts.isoformat(),
                "why": "Unusual late-night activity can be a red flag." if getattr(txn, "flag_night_transaction", False) else None,
            }
        )

    flags = [
        ("Large Transaction", bool(getattr(txn, "flag_large_transaction", False))),
        ("High-Risk Country", bool(getattr(txn, "flag_high_risk_country", False))),
        ("PEP Involved", bool(getattr(txn, "flag_pep_involved", False))),
        ("Structuring", bool(getattr(txn, "flag_structuring", False))),
        ("Dormant Account", bool(getattr(txn, "flag_dormant_account", False))),
        ("Crypto", bool(getattr(txn, "flag_crypto", False))),
    ]
    on_flags = [name for name, on in flags if on]
    if on_flags:
        highlights.append(
            {
                "label": "Triggered Signals",
                "value": ", ".join(on_flags),
                "why": "These rule-based signals contributed to the risk score.",
            }
        )

    return highlights


def explain_transaction(txn: Transaction) -> dict:
    rule_score = float(getattr(txn, "rule_score", 0) or 0)
    ml_score = float(getattr(txn, "ml_score", 0) or 0)
    graph_score = float(getattr(txn, "graph_score", 0) or 0)
    comp = float(getattr(txn, "composite_risk_score", 0) or 0)

    triggered = _flags_to_rules(txn)
    is_cross_border = bool(getattr(txn, "is_cross_border", False))

    reasons = explain_reasons(
        triggered_rules=triggered,
        is_cross_border=is_cross_border,
        ml_score=ml_score,
        composite_score=comp,
    )

    return {
        "entity_type": "transaction",
        "entity_id": str(txn.txn_id),
        "risk_label": getattr(txn, "risk_label", None),
        "composite_risk_score": comp,
        "breakdown": _breakdown(rule_score, ml_score, graph_score),
        "triggered_rules": triggered,
        "reasons": reasons,
        "highlights": _highlights_from_txn(txn),
    }


def explain_alert(alert: Alert, txn: Optional[Transaction]) -> dict:
    rule_score = float(getattr(alert, "rule_score", 0) or 0)
    ml_score = float(getattr(alert, "ml_score", 0) or 0)
    graph_score = float(getattr(alert, "graph_score", 0) or 0)
    comp = float(getattr(alert, "composite_risk_score", 0) or 0)

    triggered: list[str] = []
    if getattr(alert, "alert_rule", None):
        triggered.append(str(alert.alert_rule))
    if txn is not None:
        triggered = list(dict.fromkeys(triggered + _flags_to_rules(txn)))

    is_cross_border = bool(getattr(txn, "is_cross_border", False)) if txn is not None else False

    reasons = explain_reasons(
        triggered_rules=triggered,
        is_cross_border=is_cross_border,
        ml_score=ml_score,
        composite_score=comp,
    )

    highlights = _highlights_from_txn(txn) if txn is not None else []

    return {
        "entity_type": "alert",
        "entity_id": str(alert.alert_id),
        "risk_label": getattr(alert, "severity", None),
        "composite_risk_score": comp,
        "breakdown": _breakdown(rule_score, ml_score, graph_score),
        "triggered_rules": triggered,
        "reasons": reasons,
        "highlights": highlights,
    }
