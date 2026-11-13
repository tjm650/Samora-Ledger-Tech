from datetime import datetime, timedelta, timezone

from main import build_executive_overview


def test_executive_overview_returns_aggregate_metrics_without_customer_data():
    now = datetime(2026, 11, 12, 12, 0, tzinfo=timezone.utc)
    transactions = [
        {"transaction_id": "a1", "timestamp": (now - timedelta(days=1)).isoformat(),
         "amount": 120.0, "transaction_type": "Debit", "merchant_category": "Groceries",
         "channel": "POS", "post_transaction_balance": 500.0},
        {"transaction_id": "a2", "timestamp": (now - timedelta(days=2)).isoformat(),
         "amount": 300.0, "transaction_type": "Credit", "merchant_category": "Salary",
         "channel": "Mobile App", "post_transaction_balance": 800.0},
        {"transaction_id": "a3", "timestamp": (now - timedelta(days=40)).isoformat(),
         "amount": 100.0, "transaction_type": "Debit", "merchant_category": "Utilities",
         "channel": "Web", "post_transaction_balance": 700.0},
    ]
    insights = [
        {"churn_risk_score": 20, "primary_churn_driver": "No material risk signal",
         "evaluated_at": now.isoformat()},
        {"churn_risk_score": 75, "primary_churn_driver": "Salary Deposit Ceased",
         "evaluated_at": now.isoformat()},
        {"churn_risk_score": 45, "primary_churn_driver": "Recent Activity Declined",
         "evaluated_at": now.isoformat()},
    ]

    result = build_executive_overview(transactions, insights, now, 90)

    assert result["metrics"]["transactions_30d"] == 2
    assert result["metrics"]["debit_volume_30d"] == 120.0
    assert result["metrics"]["credit_volume_30d"] == 300.0
    assert result["metrics"]["net_flow_30d"] == 180.0
    assert result["metrics"]["high_risk_relationships"] == 1
    assert result["risk_distribution"] == [
        {"name": "Low", "count": 1},
        {"name": "Moderate", "count": 1},
        {"name": "High", "count": 1},
    ]
    assert "customers" not in result
    assert "customer_records" not in result
    assert result["transaction_trend"][-1]["date"] == now.date().isoformat()
