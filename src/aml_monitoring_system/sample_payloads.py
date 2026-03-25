"""
Shared request payload fixtures for parametrized tests.
Import these directly in test files when you need raw dicts
rather than ORM objects.
"""
from datetime import datetime, timezone


NORMAL_TXN = {
    "txn_id"         : "TXN_NORMAL_001",
    "sender_id"      : "USR_TEST_001",
    "receiver_id"    : "USR_TEST_002",
    "amount_usd"     : 250.0,
    "amount_local"   : 20750.0,
    "currency"       : "INR",
    "fx_rate_to_usd" : 83.0,
    "payment_method" : "UPI",
    "txn_type"       : "P2P",
    "timestamp"      : "2024-06-01T14:00:00Z",
    "is_cross_border": False,
    "sender_country" : "IN",
    "receiver_country": "IN",
    "channel"        : "Mobile App",
}

HIGH_RISK_TXN = {
    "txn_id"         : "TXN_HIGHRISK_002",
    "sender_id"      : "USR_TEST_001",
    "receiver_id"    : "USR_TEST_003",
    "amount_usd"     : 95_000.0,
    "amount_local"   : 95_000.0,
    "currency"       : "USD",
    "fx_rate_to_usd" : 1.0,
    "payment_method" : "SWIFT",
    "txn_type"       : "Remittance",
    "timestamp"      : "2024-06-01T02:30:00Z",   # night
    "is_cross_border": True,
    "sender_country" : "IN",
    "receiver_country": "IR",                      # sanctioned
    "channel"        : "API",
}

STRUCTURING_TXN = {
    "txn_id"         : "TXN_STRUCT_001",
    "sender_id"      : "USR_TEST_001",
    "receiver_id"    : "USR_TEST_002",
    "amount_usd"     : 7_499.0,                    # just under $10k threshold
    "amount_local"   : 622_417.0,
    "currency"       : "INR",
    "fx_rate_to_usd" : 83.0,
    "payment_method" : "NEFT",
    "txn_type"       : "P2P",
    "timestamp"      : "2024-06-01T10:00:00Z",
    "is_cross_border": False,
    "sender_country" : "IN",
    "receiver_country": "IN",
    "channel"        : "Web",
}

CRYPTO_TXN = {
    "txn_id"         : "TXN_CRYPTO_001",
    "sender_id"      : "USR_TEST_001",
    "receiver_id"    : "USR_TEST_002",
    "amount_usd"     : 15_000.0,
    "amount_local"   : 15_000.0,
    "currency"       : "BTC",
    "fx_rate_to_usd" : 1.0,
    "payment_method" : "Crypto",
    "txn_type"       : "P2P",
    "timestamp"      : "2024-06-01T14:00:00Z",
    "is_cross_border": True,
    "sender_country" : "IN",
    "receiver_country": "US",
    "channel"        : "API",
}

ALL_PAYLOADS = [NORMAL_TXN, HIGH_RISK_TXN, STRUCTURING_TXN, CRYPTO_TXN]
