import pandas as pd
from analytics import engineer_features, score_customer

def test_salary_disruption_and_velocity_features():
    now=pd.Timestamp("2026-11-11T00:00:00Z")
    rows=[
      {"customer_id":"c1","timestamp":"2026-09-01T10:00:00Z","amount":2500,"transaction_type":"Credit","merchant_category":"Salary","post_transaction_balance":3000},
      {"customer_id":"c1","timestamp":"2026-11-01T10:00:00Z","amount":120,"transaction_type":"Debit","merchant_category":"Groceries","post_transaction_balance":100},
    ]
    frame=engineer_features(pd.DataFrame(rows),now=now)
    row=frame.iloc[0]
    assert row.salary_disruption_flag is True
    assert row.recency_days == 10
    assert row.balance_avg_30d == 100

def test_rule_score_is_bounded_and_actionable():
    row=pd.Series({"salary_disruption_flag":True,"recency_days":30,"velocity_score":0.2,
      "balance_avg_30d":100,"frequency_30d":1,"discretionary_spend_ratio":0.0,"balance_drawdown_pct":0.9})
    result=score_customer(row)
    assert 0 <= result["churn_risk_score"] <= 100
    assert result["primary_churn_driver"] == "Salary Deposit Ceased"
    assert result["prescriptive_action"]
