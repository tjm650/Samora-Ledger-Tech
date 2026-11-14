"""Leakage-aware, provenance-gated supervised model training.

Production training is restricted to imported customers, imported feature rows,
and verified imported outcomes. Artifacts are uploaded only to a configured
private Supabase Storage bucket. Training never activates a model automatically.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from io import BytesIO
import json
import logging
import os
import secrets
import time
from typing import Any

import joblib
import numpy as np
import pandas as pd
from fastapi import APIRouter, Header, HTTPException
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score, average_precision_score, brier_score_loss,
    confusion_matrix, precision_score, recall_score, roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

log = logging.getLogger("samora.model_training")
router = APIRouter(tags=["model-training"])

FEATURE_SCHEMA_VERSION = "customer-behaviour-v2"
LABEL_DEFINITION_VERSION = "churn-outcome-v1"
TARGET_NAME = "churned_within_observation_window"
FEATURE_COLUMNS = [
    "recency_days", "frequency_7d", "frequency_30d", "frequency_90d",
    "frequency_180d", "monetary_spend_30d", "monetary_spend_60d",
    "monetary_spend_90d", "monetary_spend_180d", "credit_inflow_30d",
    "credit_inflow_90d", "debit_outflow_30d", "debit_outflow_90d",
    "average_transaction_value_90d", "transaction_count_90d",
    "active_days_90d", "channel_diversity_90d", "category_diversity_90d",
    "salary_inflow_90d", "product_count", "balance_avg_30d",
    "velocity_score", "discretionary_spend_ratio", "salary_disruption_flag",
    "balance_drawdown_pct",
]
PAGE_SIZE = 1000


def chronological_split(frame: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Split by outcome time, never random-shuffle temporal customer outcomes."""
    ordered = frame.sort_values(["outcome_date", "customer_id"]).reset_index(drop=True)
    n = len(ordered)
    train_end = int(n * 0.70)
    validation_end = int(n * 0.85)
    if train_end < 1 or validation_end <= train_end or validation_end >= n:
        raise ValueError("At least 20 labelled observations are required for chronological splits")
    return {
        "train": ordered.iloc[:train_end].copy(),
        "validation": ordered.iloc[train_end:validation_end].copy(),
        "test": ordered.iloc[validation_end:].copy(),
    }


def classification_metrics(y_true: np.ndarray, probabilities: np.ndarray) -> dict[str, Any]:
    """Return thresholded and ranking metrics for a binary churn classifier."""
    y_pred = (probabilities >= 0.5).astype(int)
    return {
        "sample_count": int(len(y_true)),
        "positive_count": int(np.sum(y_true)),
        "positive_rate": round(float(np.mean(y_true)), 6),
        "pr_auc": round(float(average_precision_score(y_true, probabilities)), 6),
        "roc_auc": round(float(roc_auc_score(y_true, probabilities)), 6),
        "accuracy": round(float(accuracy_score(y_true, y_pred)), 6),
        "precision_at_0_5": round(float(precision_score(y_true, y_pred, zero_division=0)), 6),
        "recall_at_0_5": round(float(recall_score(y_true, y_pred, zero_division=0)), 6),
        "brier_score": round(float(brier_score_loss(y_true, probabilities)), 6),
        "confusion_matrix": confusion_matrix(y_true, y_pred, labels=[0, 1]).tolist(),
    }


def _database():
    from supabase import create_client
    url, key = os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required")
    return create_client(url, key)


def _all_rows(db, table: str, columns: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    offset = 0
    while True:
        page = db.table(table).select(columns).range(offset, offset + PAGE_SIZE - 1).execute().data or []
        rows.extend(page)
        if len(page) < PAGE_SIZE:
            return rows
        offset += PAGE_SIZE


def _load_eligible_dataset(db) -> tuple[pd.DataFrame, dict[str, int]]:
    # Deliberately select only the columns needed for model construction.
    customers = _all_rows(db, "customers", "customer_id,data_origin,source_system,import_batch_id")
    features = _all_rows(
        db, "customer_features",
        "customer_id,data_origin,feature_as_of,feature_quality_status,feature_engine_version,"
        + ",".join(FEATURE_COLUMNS),
    )
    outcomes = _all_rows(
        db, "customer_churn_outcomes",
        "customer_id,outcome,outcome_date,outcome_window_start,outcome_window_end,"
        "label_definition_version,label_confidence,verified_at,data_origin",
    )
    customer_map = {
        str(r["customer_id"]): r for r in customers
        if r.get("customer_id") and r.get("data_origin") == "imported"
    }
    feature_map = {
        str(r["customer_id"]): r for r in features
        if r.get("customer_id") and r.get("data_origin") == "imported"
        and r.get("feature_quality_status") == "passed" and r.get("feature_as_of")
    }
    eligible_labels = [
        r for r in outcomes
        if r.get("customer_id") and r.get("data_origin") == "imported"
        and r.get("label_confidence") == "verified" and r.get("verified_at")\n        and r.get("label_definition_version") == LABEL_DEFINITION_VERSION
        and r.get("outcome") in {"churned", "retained"}
        and r.get("outcome_date") and r.get("outcome_window_start")
    ]
    # Use the latest verified observation per customer, and require features to
    # have been calculated no later than the start of the label observation.
    latest: dict[str, dict[str, Any]] = {}
    for label in eligible_labels:
        cid = str(label["customer_id"])
        if cid not in latest or str(label["outcome_date"]) > str(latest[cid]["outcome_date"]):
            latest[cid] = label

    rows = []
    for cid, label in latest.items():
        if cid not in customer_map or cid not in feature_map:
            continue
        feature = feature_map[cid]
        try:
            if pd.Timestamp(feature["feature_as_of"]) > pd.Timestamp(label["outcome_window_start"]):
                continue
        except (TypeError, ValueError):
            continue
        row = {column: feature.get(column) for column in FEATURE_COLUMNS}
        row.update({
            "customer_id": cid,
            "outcome_date": str(label["outcome_date"]),
            "target": 1 if label["outcome"] == "churned" else 0,
        })
        rows.append(row)
    frame = pd.DataFrame(rows)
    counts = {
        "customer_records_total": len(customers),
        "imported_customers": len(customer_map),
        "feature_records_total": len(features),
        "eligible_imported_feature_records": len(feature_map),
        "outcome_records_total": len(outcomes),
        "verified_imported_binary_outcomes": len(eligible_labels),
        "eligible_training_rows": len(frame),
        "excluded_mock_or_unclassified_customers": len(customers) - len(customer_map),
        "excluded_non_imported_or_unverified_outcomes": len(outcomes) - len(eligible_labels),
    }
    return frame, counts


def get_training_readiness() -> dict[str, Any]:
    db = _database()
    frame, counts = _load_eligible_dataset(db)
    reasons = []
    if len(frame) < 120:
        reasons.append("At least 120 eligible labelled customer observations are required.")
    if len(frame) and frame["target"].nunique() < 2:
        reasons.append("Both churned and retained outcomes are required.")
    if not os.getenv("MODEL_ARTIFACT_BUCKET"):
        reasons.append("MODEL_ARTIFACT_BUCKET must point to a private Supabase Storage bucket.")
    if not (os.getenv("GIT_COMMIT_SHA") or os.getenv("RENDER_GIT_COMMIT")):
        reasons.append("GIT_COMMIT_SHA should be configured for reproducible model lineage.")
    return {
        "status": "ready" if not reasons else "blocked",
        "production_training_allowed": not reasons,
        "model_type": "churn_classification",
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "label_definition_version": LABEL_DEFINITION_VERSION,
        "counts": counts,
        "blockers": reasons,
        "mock_data_policy": "Mock, synthetic, test, mixed and unclassified records are excluded.",
        "training_side_effects": "Readiness check is read-only.",
    }


def run_churn_training() -> dict[str, Any]:
    started = time.monotonic()
    db = _database()
    frame, counts = _load_eligible_dataset(db)
    if len(frame) < 120 or frame["target"].nunique() < 2:
        raise ValueError("Training blocked: insufficient eligible imported and verified churn outcomes.")
    bucket = os.getenv("MODEL_ARTIFACT_BUCKET")
    if not bucket:
        raise ValueError("Training blocked: configure MODEL_ARTIFACT_BUCKET as a private bucket.")
    if not os.getenv("GIT_COMMIT_SHA"):
        raise ValueError("Training blocked: configure GIT_COMMIT_SHA for reproducibility.")

    splits = chronological_split(frame)
    for name, part in splits.items():
        if part["target"].nunique() < 2:
            raise ValueError(f"Training blocked: {name} split must contain both churned and retained outcomes.")
    x = {name: part[FEATURE_COLUMNS].apply(pd.to_numeric, errors="coerce") for name, part in splits.items()}
    y = {name: part["target"].astype(int).to_numpy() for name, part in splits.items()}

    candidates = {
        "logistic_regression": Pipeline([
            ("imputer", SimpleImputer(strategy="median", add_indicator=True)),
            ("scaler", StandardScaler()),
            ("classifier", LogisticRegression(class_weight="balanced", max_iter=1500, random_state=42)),
        ]),
        "random_forest": Pipeline([
            ("imputer", SimpleImputer(strategy="median", add_indicator=True)),
            ("classifier", RandomForestClassifier(
                n_estimators=400, min_samples_leaf=3, class_weight="balanced_subsample",
                max_features="sqrt", random_state=42, n_jobs=-1,
            )),
        ]),
    }
    comparisons = {}
    fitted = {}
    for name, estimator in candidates.items():
        estimator.fit(x["train"], y["train"])
        probabilities = estimator.predict_proba(x["validation"])[:, 1]
        comparisons[name] = classification_metrics(y["validation"], probabilities)
        fitted[name] = estimator
    winner_name = max(comparisons, key=lambda name: comparisons[name]["pr_auc"])
    winner = fitted[winner_name]
    validation_metrics = comparisons[winner_name]
    test_probabilities = winner.predict_proba(x["test"])[:, 1]
    test_metrics = classification_metrics(y["test"], test_probabilities)
    train_metrics = classification_metrics(y["train"], winner.predict_proba(x["train"])[:, 1])

    # Dataset manifest contains aggregate metadata only; no customer identifiers.
    manifest = {
        "model_type": "churn_classification",
        "target_name": TARGET_NAME,
        "data_origin": "imported",
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "label_definition_version": LABEL_DEFINITION_VERSION,
        "feature_columns": FEATURE_COLUMNS,
        "split_strategy": "chronological_70_15_15_by_outcome_date",
        "split_counts": {k: len(v) for k, v in splits.items()},
        "class_counts": {k: {str(c): int((v["target"] == c).sum()) for c in (0, 1)} for k, v in splits.items()},
        "eligible_counts": counts,
        "observation_start": str(frame["outcome_date"].min()),
        "observation_end": str(frame["outcome_date"].max()),
        "code_commit_sha": (os.getenv("GIT_COMMIT_SHA") or os.getenv("RENDER_GIT_COMMIT")),
    }
    digest_payload = {
        "manifest": manifest,
        "rows": frame[["customer_id", "outcome_date", "target"]].sort_values(
            ["outcome_date", "customer_id"]
        ).to_dict(orient="records"),
        "feature_values": frame[FEATURE_COLUMNS].replace({np.nan: None}).to_dict(orient="records"),
    }
    dataset_checksum = sha256(
        json.dumps(digest_payload, sort_keys=True, default=str, separators=(",", ":")).encode()
    ).hexdigest()
    dataset_version = f"churn-{dataset_checksum[:16]}"
    artifact_buffer = BytesIO()
    joblib.dump({
        "estimator": winner,
        "feature_columns": FEATURE_COLUMNS,
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "target_name": TARGET_NAME,
        "selected_algorithm": winner_name,
    }, artifact_buffer)
    artifact_bytes = artifact_buffer.getvalue()
    artifact_checksum = sha256(artifact_bytes).hexdigest()
    artifact_path = f"experimental/churn/{dataset_checksum}/{winner_name}.joblib"
    db.storage.from_(bucket).upload(
        artifact_path, artifact_bytes,
        file_options={"content-type": "application/octet-stream", "upsert": "true"},
    )
    artifact_uri = f"supabase://{bucket}/{artifact_path}"

    dataset_insert = db.table("model_datasets").insert({
        "dataset_name": "bancabc_verified_churn_training",
        "dataset_version": dataset_version,
        "model_type": "churn_classification",
        "target_name": TARGET_NAME,
        "data_origin": "imported",
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "label_definition_version": LABEL_DEFINITION_VERSION,
        "observation_start": manifest["observation_start"],
        "observation_end": manifest["observation_end"],
        "row_count": len(frame),
        "customer_count": int(frame["customer_id"].nunique()),
        "feature_columns": FEATURE_COLUMNS,
        "excluded_columns": ["customer_id", "outcome_date", "target"],
        "split_strategy": manifest["split_strategy"],
        "dataset_checksum": dataset_checksum,
        "manifest": manifest,
    }).execute().data or []
    if not dataset_insert:
        raise RuntimeError("Dataset manifest could not be persisted")
    dataset_id = dataset_insert[0]["dataset_id"]

    trained_at = datetime.now(timezone.utc)
    version_insert = db.table("model_versions").insert({
        "version": f"churn-{trained_at.strftime('%Y%m%d%H%M%S')}-{dataset_checksum[:8]}",
        "model_type": "machine_learning",
        "description": "Experimental churn classifier selected by chronological validation PR-AUC.",
        "is_active": False,
        "algorithm": winner_name,
        "target_name": TARGET_NAME,
        "task_type": "binary_classification",
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "hyperparameters": {"candidate_algorithms": list(candidates), "selection_metric": "validation_pr_auc"},
        "training_dataset_id": dataset_id,
        "artifact_uri": artifact_uri,
        "artifact_checksum": artifact_checksum,
        "training_started_at": datetime.fromtimestamp(time.time() - (time.monotonic() - started), timezone.utc).isoformat(),
        "trained_at": trained_at.isoformat(),
        "validation_metrics": validation_metrics,
        "approval_status": "experimental",
        "code_commit_sha": os.environ["GIT_COMMIT_SHA"],
    }).execute().data or []
    if not version_insert:
        raise RuntimeError("Experimental model registry entry could not be persisted")
    version_id = version_insert[0]["model_version_id"]

    run_insert = db.table("model_runs").insert({
        "model_version_id": version_id,
        "status": "completed",
        "run_type": "training",
        "customers_evaluated": len(frame),
        "records_skipped": counts["customer_records_total"] - len(frame),
        "records_failed": 0,
        "started_at": datetime.fromtimestamp(time.time() - (time.monotonic() - started), timezone.utc).isoformat(),
        "completed_at": trained_at.isoformat(),
        "execution_duration_ms": int((time.monotonic() - started) * 1000),
        "metrics": {"validation": validation_metrics, "test": test_metrics, "train": train_metrics, "model_comparison": comparisons},
        "dataset_id": dataset_id,
        "data_cutoff_at": pd.Timestamp(frame["outcome_date"].max()).isoformat(),
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "code_commit_sha": os.environ["GIT_COMMIT_SHA"],
        "environment_name": os.getenv("APP_ENV", "production"),
        "warnings": ["EXPERIMENTAL_NOT_APPROVED", "OUT_OF_TIME_TEST_IS_HOLDOUT_NOT_PRODUCTION_CERTIFICATION"],
        "run_metadata": {"dataset_checksum": dataset_checksum, "artifact_checksum": artifact_checksum},
    }).execute().data or []
    run_id = run_insert[0]["model_run_id"] if run_insert else None

    for split_name, metrics in (("train", train_metrics), ("validation", validation_metrics), ("test", test_metrics)):
        db.table("model_evaluations").insert({
            "model_version_id": version_id,
            "model_run_id": run_id,
            "dataset_id": dataset_id,
            "evaluation_name": f"churn-{split_name}",
            "split_name": split_name,
            "sample_count": metrics["sample_count"],
            "positive_count": metrics["positive_count"],
            "metrics": {k: v for k, v in metrics.items() if k != "confusion_matrix"},
            "confusion_matrix": metrics["confusion_matrix"],
            "acceptance_status": "not_reviewed",
            "notes": "Experimental evaluation; requires independent review before approval.",
        }).execute()

    return {
        "status": "completed_experimental",
        "production_approved": False,
        "selected_algorithm": winner_name,
        "model_version_id": version_id,
        "model_run_id": run_id,
        "dataset_id": dataset_id,
        "dataset_checksum": dataset_checksum,
        "artifact_checksum": artifact_checksum,
        "artifact_uri": artifact_uri,
        "split_metrics": {"train": train_metrics, "validation": validation_metrics, "test": test_metrics},
        "model_comparison": comparisons,
        "eligible_counts": counts,
        "duration_ms": int((time.monotonic() - started) * 1000),
    }


def _authorize(x_api_key: str | None) -> None:
    expected = os.getenv("API_KEY")
    if not expected:
        raise HTTPException(503, "API_KEY is not configured")
    if not x_api_key or not secrets.compare_digest(x_api_key, expected):
        raise HTTPException(401, "Invalid API key")


@router.get("/api/v1/model-training/readiness")
def model_training_readiness(x_api_key: str | None = Header(default=None)):
    _authorize(x_api_key)
    try:
        return get_training_readiness()
    except Exception as exc:
        log.exception("Model training readiness check failed")
        raise HTTPException(500, "Unable to inspect model training readiness") from exc


@router.post("/api/v1/model-training/churn")
def train_churn_model(x_api_key: str | None = Header(default=None)):
    _authorize(x_api_key)
    try:
        return run_churn_training()
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    except Exception as exc:
        log.exception("Churn model training failed")
        raise HTTPException(500, "Model training failed; inspect backend logs") from exc
