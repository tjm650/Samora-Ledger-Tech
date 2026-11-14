import pandas as pd

from development_model_training import prepare_mock_feature_frame


def test_mock_segmentation_frame_only_uses_mock_customers_and_passed_features():
    customers = [
        {"customer_id": "mock-1", "data_origin": "mock"},
        {"customer_id": "imported-1", "data_origin": "imported"},
    ]
    features = [
        {"customer_id": "mock-1", "data_origin": "mock", "feature_quality_status": "passed",
         "recency_days": 12, "frequency_30d": 8, "monetary_spend_90d": 120.0},
        {"customer_id": "imported-1", "data_origin": "imported", "feature_quality_status": "passed",
         "recency_days": 4, "frequency_30d": 30, "monetary_spend_90d": 900.0},
        {"customer_id": "mock-1", "data_origin": "mock", "feature_quality_status": "failed",
         "recency_days": 90, "frequency_30d": 0, "monetary_spend_90d": 0.0},
    ]
    frame = prepare_mock_feature_frame(customers, features)
    assert frame["customer_id"].tolist() == ["mock-1"]
    assert frame.loc[0, "recency_days"] == 12
    assert "customer_id" in frame.columns


def test_mock_segmentation_frame_returns_empty_without_eligible_mock_features():
    customers = [{"customer_id": "c1", "data_origin": "mock"}]
    features = [{"customer_id": "c1", "data_origin": "mock", "feature_quality_status": "failed"}]
    frame = prepare_mock_feature_frame(customers, features)
    assert frame.empty


from development_model_training import _segment_interpretation


def test_segment_interpretation_uses_relative_portfolio_medians():
    profile = {"frequency_30d": 40, "monetary_spend_90d": 900}
    overall = {"frequency_30d": 20, "monetary_spend_90d": 500}
    name, summary, signals = _segment_interpretation(profile, overall, 100, 1000)
    assert name == "Highly active, higher spend"
    assert "above the portfolio median" in summary
    assert len(signals) == 2


def test_small_segment_is_flagged_in_interpretation():
    profile = {"frequency_30d": 10}
    overall = {"frequency_30d": 20}
    _, summary, _ = _segment_interpretation(profile, overall, 7, 1000)
    assert "very small cluster" in summary
