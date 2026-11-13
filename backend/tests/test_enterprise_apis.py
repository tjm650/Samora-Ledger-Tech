import pandas as pd
import pytest
from pydantic import ValidationError

from analytics import engineer_features, score_customer
from crm_api import InteractionCreate, TaskCreate, TaskPatch, RiskThresholdUpdate
from management_api import ReportRequest


def test_feature_engineering_persists_multi_period_spend_fields():
    now = pd.Timestamp("2026-11-13T00:00:00Z")
    rows = [
        {"customer_id":"c1","timestamp":"2026-09-01T10:00:00Z","amount":500,"transaction_type":"Debit","merchant_category":"Groceries","post_transaction_balance":1500},
        {"customer_id":"c1","timestamp":"2026-10-20T10:00:00Z","amount":300,"transaction_type":"Debit","merchant_category":"Travel","post_transaction_balance":1200},
        {"customer_id":"c1","timestamp":"2026-11-05T10:00:00Z","amount":100,"transaction_type":"Debit","merchant_category":"Utilities","post_transaction_balance":1000},
        {"customer_id":"c1","timestamp":"2026-11-10T10:00:00Z","amount":1000,"transaction_type":"Credit","merchant_category":"Salary","post_transaction_balance":2000},
    ]
    row = engineer_features(pd.DataFrame(rows), now=now).iloc[0]
    assert row.monetary_spend_30d == 400
    assert row.monetary_spend_60d == 400
    assert row.monetary_spend_90d == 900
    assert row.average_transaction_value_90d == 475


def test_crm_interaction_validation():
    item = InteractionCreate(interaction_type="call", subject="Retention check-in", notes="Customer requested follow-up")
    assert item.interaction_type == "call"
    with pytest.raises(ValidationError):
        InteractionCreate(interaction_type="invalid", subject="bad")


def test_crm_task_requires_customer_and_valid_priority():
    from uuid import uuid4
    task = TaskCreate(customer_id=uuid4(), title="Call customer", priority="urgent")
    assert task.priority == "urgent"
    with pytest.raises(ValidationError):
        TaskCreate(customer_id=uuid4(), title="Invalid", priority="critical")


def test_risk_thresholds_must_be_ordered_by_endpoint_validation():
    threshold = RiskThresholdUpdate(low_max=29.99, moderate_max=59.99, significant_movement=15)
    assert threshold.moderate_max > threshold.low_max


def test_report_period_is_explicit_and_validated():
    report = ReportRequest(report_key="executive_summary", period_start="2026-10-01", period_end="2026-10-31")
    assert report.period_end >= report.period_start


def test_versioned_scoring_configuration_changes_rule_contribution():
    row = pd.Series({
        "salary_disruption_flag": True, "recency_days": 0, "velocity_score": 1.0,
        "balance_avg_30d": 5000, "frequency_30d": 10,
        "discretionary_spend_ratio": 0.2, "balance_drawdown_pct": 0.1
    })
    baseline = score_customer(row, {"base_score": 5, "salary_disruption_points": 10})
    assert baseline["churn_risk_score"] == 15
