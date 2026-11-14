import numpy as np
import pandas as pd
import pytest

from model_training import chronological_split, classification_metrics


def test_chronological_split_keeps_time_order_and_expected_proportions():
    frame = pd.DataFrame({
        "customer_id": [f"c{i}" for i in range(100)],
        "outcome_date": pd.date_range("2025-01-01", periods=100, freq="D").astype(str),
        "target": [i % 2 for i in range(100)],
    })
    parts = chronological_split(frame)
    assert [len(parts[k]) for k in ("train", "validation", "test")] == [70, 15, 15]
    assert parts["train"]["outcome_date"].max() < parts["validation"]["outcome_date"].min()
    assert parts["validation"]["outcome_date"].max() < parts["test"]["outcome_date"].min()


def test_chronological_split_rejects_too_small_dataset():
    frame = pd.DataFrame({
        "customer_id": ["a", "b"],
        "outcome_date": ["2025-01-01", "2025-01-02"],
        "target": [0, 1],
    })
    with pytest.raises(ValueError):
        chronological_split(frame)


def test_classification_metrics_reports_ranking_calibration_and_threshold_metrics():
    y = np.array([0, 0, 1, 1])
    probabilities = np.array([0.1, 0.4, 0.6, 0.9])
    result = classification_metrics(y, probabilities)
    assert result["pr_auc"] == 1.0
    assert result["roc_auc"] == 1.0
    assert result["accuracy"] == 1.0
    assert result["brier_score"] < 0.1
    assert result["confusion_matrix"] == [[2, 0], [0, 2]]
