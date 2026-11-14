"""Development-only unsupervised behavioural segmentation on mock Supabase data.

This deliberately does not manufacture churn labels. It clusters mock customer
features for pipeline/integration experimentation only; outputs are not churn
probabilities, customer risk scores, or production evidence.
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
from sklearn.cluster import KMeans
from sklearn.impute import SimpleImputer
from sklearn.metrics import silhouette_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

log = logging.getLogger("samora.development_training")
router = APIRouter(tags=["development-model-training"])
PAGE_SIZE = 1000
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
SCHEMA_VERSION = "customer-behaviour-v2"


def _authorize(key: str | None) -> None:
    expected = os.getenv("API_KEY")
    if not expected:
        raise HTTPException(503, "API_KEY is not configured")
    if not key or not secrets.compare_digest(key, expected):
        raise HTTPException(401, "Invalid API key")


def _database():
    from supabase import create_client
    url, key = os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise RuntimeError("Supabase service configuration is missing")
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


def prepare_mock_feature_frame(customers: list[dict[str, Any]], features: list[dict[str, Any]]) -> pd.DataFrame:
    """Join only explicitly mock customers/features with passed feature quality."""
    allowed = {
        str(row["customer_id"]) for row in customers
        if row.get("customer_id") and row.get("data_origin") == "mock"
    }
    rows = [
        row for row in features
        if row.get("customer_id") and str(row["customer_id"]) in allowed
        and row.get("data_origin") == "mock"
        and row.get("feature_quality_status") == "passed"
    ]
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    frame = frame.drop_duplicates(subset=["customer_id"], keep="last")
    for column in FEATURE_COLUMNS:
        if column not in frame:
            frame[column] = np.nan
    frame[FEATURE_COLUMNS] = frame[FEATURE_COLUMNS].apply(pd.to_numeric, errors="coerce")
    frame = frame.replace([np.inf, -np.inf], np.nan)
    frame = frame.dropna(axis=1, how="all")
    return frame


def run_mock_segmentation() -> dict[str, Any]:
    started = time.monotonic()
    db = _database()
    customers = _all_rows(db, "customers", "customer_id,data_origin")
    features = _all_rows(db, "customer_features", "customer_id,data_origin,feature_quality_status,feature_as_of," + ",".join(FEATURE_COLUMNS))
    frame = prepare_mock_feature_frame(customers, features)
    if len(frame) < 30:
        raise ValueError("At least 30 quality-passed mock customer feature rows are required.")
    if len(FEATURE_COLUMNS) == 0:
        raise ValueError("No behavioural features are configured.")
    bucket = os.getenv("MODEL_ARTIFACT_BUCKET")
    if not bucket:
        raise ValueError("MODEL_ARTIFACT_BUCKET must point to a private Supabase Storage bucket.")
    commit = os.getenv("GIT_COMMIT_SHA") or os.getenv("RENDER_GIT_COMMIT")
    if not commit:
        raise ValueError("A deployed source commit is required for experiment lineage.")

    # Remove columns that are entirely missing; retain a stable input schema in the artifact.
    usable_columns = [c for c in FEATURE_COLUMNS if frame[c].notna().any()]
    x = frame[usable_columns]
    if len(usable_columns) < 2:
        raise ValueError("At least two populated behavioural features are required.")
    n_clusters = min(4, max(2, len(frame) // 50))
    estimator = Pipeline([
        ("imputer", SimpleImputer(strategy="median", add_indicator=True)),
        ("scaler", StandardScaler()),
        ("clusterer", KMeans(n_clusters=n_clusters, random_state=42, n_init=20)),
    ])
    labels = estimator.fit_predict(x)
    transformed = estimator[:-1].transform(x)
    silhouette = float(silhouette_score(transformed, labels)) if len(set(labels)) > 1 else None
    cluster_counts = {str(int(k)): int(v) for k, v in zip(*np.unique(labels, return_counts=True))}
    trained_at = datetime.now(timezone.utc)
    manifest = {
        "purpose": "development_only_mock_behavioural_segmentation",
        "data_origin": "mock",
        "production_eligible": False,
        "not_a_churn_model": True,
        "label_policy": "No churn labels generated or inferred; unsupervised clusters only.",
        "feature_schema_version": SCHEMA_VERSION,
        "feature_columns": usable_columns,
        "algorithm": "kmeans",
        "n_clusters": n_clusters,
        "row_count": len(frame),
        "cluster_counts": cluster_counts,
        "feature_quality_filter": "passed",
        "code_commit_sha": commit,
    }
    digest_payload = {
        "manifest": manifest,
        "features": frame[["customer_id"] + usable_columns].sort_values("customer_id").replace({np.nan: None}).to_dict(orient="records"),
    }
    dataset_checksum = sha256(json.dumps(digest_payload, sort_keys=True, default=str, separators=(",", ":")).encode()).hexdigest()
    artifact_buffer = BytesIO()
    joblib.dump({
        "estimator": estimator, "feature_columns": usable_columns,
        "feature_schema_version": SCHEMA_VERSION,
        "model_purpose": "development_only_mock_behavioural_segmentation",
        "production_eligible": False, "not_a_churn_model": True,
    }, artifact_buffer)
    artifact_bytes = artifact_buffer.getvalue()
    artifact_checksum = sha256(artifact_bytes).hexdigest()
    artifact_path = f"development-only/mock-segmentation/{dataset_checksum}/kmeans.joblib"
    db.storage.from_(bucket).upload(
        artifact_path, artifact_bytes,
        file_options={"content-type": "application/octet-stream", "upsert": "true"},
    )
    artifact_uri = f"supabase://{bucket}/{artifact_path}"

    dataset_row = db.table("model_datasets").insert({
        "dataset_name": "development_mock_customer_behaviour_segments",
        "dataset_version": f"mock-segments-{dataset_checksum[:16]}",
        "model_type": "customer_behaviour_segmentation",
        "target_name": "unsupervised_cluster_assignment",
        "data_origin": "mock",
        "feature_schema_version": SCHEMA_VERSION,
        "label_definition_version": "none_unsupervised",
        "row_count": len(frame),
        "customer_count": int(frame["customer_id"].nunique()),
        "feature_columns": usable_columns,
        "excluded_columns": ["customer_id", "cluster_assignment"],
        "split_strategy": "unsupervised_full_mock_feature_snapshot",
        "dataset_checksum": dataset_checksum,
        "manifest": manifest,
    }).execute().data or []
    if not dataset_row:
        raise RuntimeError("Could not persist mock development dataset manifest")
    dataset_id = dataset_row[0]["dataset_id"]

    version_row = db.table("model_versions").insert({
        "version": f"mock-segments-{trained_at.strftime('%Y%m%d%H%M%S')}-{dataset_checksum[:8]}",
        "model_type": "machine_learning",
        "description": "DEVELOPMENT ONLY: K-means behavioural segmentation trained on mock data; not a churn model.",
        "is_active": False,
        "algorithm": "kmeans",
        "target_name": "unsupervised_cluster_assignment",
        "task_type": "clustering",
        "feature_schema_version": SCHEMA_VERSION,
        "hyperparameters": {"n_clusters": n_clusters, "random_state": 42, "n_init": 20},
        "training_dataset_id": dataset_id,
        "artifact_uri": artifact_uri,
        "artifact_checksum": artifact_checksum,
        "training_started_at": trained_at.isoformat(),
        "trained_at": trained_at.isoformat(),
        "validation_metrics": {"silhouette_score": silhouette, "cluster_counts": cluster_counts},
        "approval_status": "experimental",
        "code_commit_sha": commit,
    }).execute().data or []
    if not version_row:
        raise RuntimeError("Could not register development-only model")
    version_id = version_row[0]["model_version_id"]

    duration_ms = int((time.monotonic() - started) * 1000)
    run_row = db.table("model_runs").insert({
        "model_version_id": version_id,
        "status": "completed",
        "run_type": "training",
        "customers_evaluated": len(frame),
        "records_skipped": max(0, len(customers) - len(frame)),
        "records_failed": 0,
        "started_at": trained_at.isoformat(),
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "execution_duration_ms": duration_ms,
        "metrics": {"silhouette_score": silhouette, "cluster_counts": cluster_counts},
        "dataset_id": dataset_id,
        "feature_schema_version": SCHEMA_VERSION,
        "code_commit_sha": commit,
        "environment_name": "development",
        "warnings": ["MOCK_DATA_ONLY", "UNSUPERVISED_SEGMENTATION_NOT_CHURN_PREDICTION", "NOT_FOR_CUSTOMER_DECISIONS"],
        "run_metadata": {"dataset_checksum": dataset_checksum, "artifact_checksum": artifact_checksum, "production_eligible": False},
    }).execute().data or []
    run_id = run_row[0]["model_run_id"] if run_row else None
    db.table("model_evaluations").insert({
        "model_version_id": version_id,
        "model_run_id": run_id,
        "dataset_id": dataset_id,
        "evaluation_name": "mock-segmentation-fit",
        "split_name": "train",
        "sample_count": len(frame),
        "metrics": {"silhouette_score": silhouette, "cluster_count": n_clusters, "cluster_counts": cluster_counts},
        "acceptance_status": "not_reviewed",
        "notes": "Mock-only unsupervised development experiment. Not churn prediction and not valid production evaluation.",
    }).execute()

    return {
        "status": "completed_development_only",
        "production_approved": False,
        "production_eligible": False,
        "model_purpose": "customer_behaviour_segmentation",
        "not_a_churn_model": True,
        "algorithm": "kmeans",
        "model_version_id": version_id,
        "model_run_id": run_id,
        "dataset_id": dataset_id,
        "customers_trained": len(frame),
        "features_used": usable_columns,
        "cluster_counts": cluster_counts,
        "silhouette_score": silhouette,
        "artifact_uri": artifact_uri,
        "duration_ms": duration_ms,
        "warnings": manifest["label_policy"],
    }


@router.post("/api/v1/model-training/development-segmentation")
def train_development_segmentation(x_api_key: str | None = Header(default=None)):
    _authorize(x_api_key)
    try:
        return run_mock_segmentation()
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    except Exception as exc:
        log.exception("Development-only mock segmentation failed")
        raise HTTPException(500, "Development-only model training failed; inspect backend logs") from exc
