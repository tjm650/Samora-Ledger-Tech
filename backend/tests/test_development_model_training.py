import pandas as pd

from fastapi import HTTPException
import pytest

from development_model_training import (
    _verify_profile_artifact_checksum,
    prepare_mock_feature_frame,
)


def test_mock_segmentation_frame_only_uses_mock_customers_and_passed_features():
    customers = [
        {"customer_id": "mock-1", "data_origin": "mock"},
        {"customer_id": "imported-1", "data_origin": "imported"},
    ]
    features = [
        {"customer_id": "mock-1", "data_origin": "mock", "feature_quality_status": "passed",
         "recency_days": 12, "frequency_7d": 2, "frequency_30d": 8, "monetary_spend_30d": 30.0, "monetary_spend_90d": 120.0,
         "credit_inflow_90d": 100.0, "debit_outflow_90d": 120.0},
        {"customer_id": "imported-1", "data_origin": "imported", "feature_quality_status": "passed",
         "recency_days": 4, "frequency_30d": 30, "monetary_spend_90d": 900.0},
        {"customer_id": "mock-1", "data_origin": "mock", "feature_quality_status": "failed",
         "recency_days": 90, "frequency_30d": 0, "monetary_spend_90d": 0.0},
    ]
    frame = prepare_mock_feature_frame(customers, features)
    assert frame["customer_id"].tolist() == ["mock-1"]
    assert frame.loc[0, "recency_days"] == 12
    assert frame.loc[0, "net_cashflow_90d"] == -20
    assert "debit_to_credit_ratio_90d" in frame.columns
    assert "monthly_spend_trend_30d_vs_90d" in frame.columns
    assert "activity_consistency_7d_vs_30d" in frame.columns
    # Optional source features remain in the schema as NaN when unpopulated.
    assert "frequency_180d" in frame.columns
    assert pd.isna(frame.loc[0, "frequency_180d"])
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
    assert len(signals) == 2
    assert all("above portfolio median" in signal for signal in signals)


def test_small_segment_is_flagged_in_interpretation():
    profile = {"frequency_30d": 10}
    overall = {"frequency_30d": 20}
    _, summary, _ = _segment_interpretation(profile, overall, 7, 1000)
    assert "very small cluster" in summary



def test_profile_artifact_checksum_accepts_matching_artifact():
    from hashlib import sha256

    artifact = b"trusted model artifact"
    _verify_profile_artifact_checksum(artifact, sha256(artifact).hexdigest())


def test_profile_artifact_checksum_rejects_modified_artifact():
    with pytest.raises(HTTPException) as exc:
        _verify_profile_artifact_checksum(b"modified artifact", "0" * 64)

    assert exc.value.status_code == 409


def test_profile_artifact_checksum_rejects_missing_checksum():
    with pytest.raises(HTTPException) as exc:
        _verify_profile_artifact_checksum(b"artifact", None)

    assert exc.value.status_code == 409



def test_read_only_cluster_comparison_reports_seed_stability_without_registry_writes(monkeypatch):
    import development_model_training as module

    monkeypatch.setenv("API_KEY", "test-key")
    customers = [{"customer_id": f"mock-{i}", "data_origin": "mock"} for i in range(60)]
    features = []
    for i in range(60):
        features.append({
            "customer_id": f"mock-{i}", "data_origin": "mock",
            "feature_quality_status": "passed",
            "recency_days": float(i % 20),
            "frequency_30d": float((i // 20) * 15 + (i % 5)),
            "frequency_90d": float((i // 20) * 30 + (i % 7)),
            "credit_inflow_90d": 0.0,
            "debit_outflow_90d": 120.0,
            "monetary_spend_30d": 30.0,
            "monetary_spend_90d": 90.0,
            "frequency_7d": 2.0,
        })
    monkeypatch.setattr(module, "_database", lambda: object())
    monkeypatch.setattr(
        module, "_all_rows",
        lambda db, table, columns: customers if table == "customers" else features,
    )

    result = module.compare_development_segmentation("test-key")

    assert result["status"] == "completed_read_only_development_comparison"
    assert result["data_origin"] == "mock"
    assert result["customers_evaluated"] == 60
    assert result["random_seeds"] == [7, 21, 42, 84, 126]
    assert [row["cluster_count"] for row in result["comparison"]] == [2, 3, 4, 5]
    assert all(row["stability_ari_mean"] is not None for row in result["comparison"])
    assert all(row["silhouette_mean"] is not None for row in result["comparison"])
    assert result["production_eligible"] is False
    assert result["not_a_churn_model"] is True
