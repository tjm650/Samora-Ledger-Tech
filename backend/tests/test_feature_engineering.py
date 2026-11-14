from datetime import datetime, timezone
import pandas as pd

from feature_engineering import calculate_customer_features


def test_features_are_cutoff_anchored_and_never_have_negative_recency():
    cutoff = datetime(2026, 11, 14, tzinfo=timezone.utc)
    tx = pd.DataFrame([
        {"customer_id": "c1", "timestamp": "2026-11-13T12:00:00Z", "amount": 100,
         "transaction_type": "Debit", "merchant_category": "Groceries",
         "channel": "Mobile App", "post_transaction_balance": 900,
         "transaction_status": "posted"},
        {"customer_id": "c1", "timestamp": "2026-11-15T12:00:00Z", "amount": 500,
         "transaction_type": "Debit", "merchant_category": "Luxury",
         "channel": "Web", "post_transaction_balance": 400,
         "transaction_status": "posted"},
    ])
    rows, quality = calculate_customer_features(tx, ["c1"], as_of=cutoff)
    assert rows[0]["recency_days"] == 0
    assert rows[0]["frequency_30d"] == 1
    assert rows[0]["monetary_spend_30d"] == 100
    assert quality["future_transactions_excluded"] == 1


def test_non_posted_transactions_are_not_counted():
    cutoff = datetime(2026, 11, 14, tzinfo=timezone.utc)
    tx = pd.DataFrame([
        {"customer_id": "c1", "timestamp": "2026-11-13T12:00:00Z", "amount": 100,
         "transaction_type": "Debit", "merchant_category": "Groceries",
         "channel": "Mobile App", "post_transaction_balance": 900,
         "transaction_status": "reversed"},
    ])
    rows, quality = calculate_customer_features(tx, ["c1"], as_of=cutoff)
    assert rows[0]["frequency_30d"] == 0
    assert rows[0]["recency_days"] is None
    assert quality["non_posted_transactions_excluded"] == 1


def test_customer_without_transactions_has_null_recency_and_zero_activity():
    cutoff = datetime(2026, 11, 14, tzinfo=timezone.utc)
    rows, _ = calculate_customer_features(pd.DataFrame(), ["c1"], as_of=cutoff)
    assert rows[0]["recency_days"] is None
    assert rows[0]["frequency_90d"] == 0
    assert rows[0]["feature_quality_status"] == "insufficient_history"


def test_salary_disruption_requires_prior_payroll_pattern():
    cutoff = datetime(2026, 11, 14, tzinfo=timezone.utc)
    tx = pd.DataFrame([
        {"customer_id": "c1", "timestamp": "2026-08-01T12:00:00Z", "amount": 1000,
         "transaction_type": "Credit", "merchant_category": "Salary",
         "channel": "Web", "post_transaction_balance": 1200,
         "transaction_status": "posted"},
        {"customer_id": "c1", "timestamp": "2026-09-01T12:00:00Z", "amount": 1000,
         "transaction_type": "Credit", "merchant_category": "Salary",
         "channel": "Web", "post_transaction_balance": 2200,
         "transaction_status": "posted"},
    ])
    rows, _ = calculate_customer_features(tx, ["c1"], as_of=cutoff)
    assert rows[0]["salary_disruption_flag"] is True
