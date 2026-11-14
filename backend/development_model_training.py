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
from sklearn.metrics import adjusted_rand_score, silhouette_score
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


PROFILE_FEATURES = {
    "recency_days": "Days since last transaction",
    "frequency_7d": "Transactions in 7 days",
    "frequency_30d": "Transactions in 30 days",
    "frequency_90d": "Transactions in 90 days",
    "frequency_180d": "Transactions in 180 days",
    "monetary_spend_30d": "Debit spend in 30 days",
    "monetary_spend_90d": "Debit spend in 90 days",
    "monetary_spend_180d": "Debit spend in 180 days",
    "credit_inflow_90d": "Credit inflow in 90 days",
    "debit_outflow_90d": "Debit outflow in 90 days",
    "average_transaction_value_90d": "Average transaction value",
    "active_days_90d": "Active days in 90 days",
    "channel_diversity_90d": "Channel diversity",
    "category_diversity_90d": "Category diversity",
    "salary_inflow_90d": "Salary inflow in 90 days",
    "balance_avg_30d": "Average balance in 30 days",
    "velocity_score": "Transaction velocity score",
}

def _segment_interpretation(profile: dict[str, float], overall: dict[str, float], size: int, total: int) -> tuple[str, str, list[str]]:
    signals = []
    for key in ("frequency_30d", "frequency_90d", "monetary_spend_90d", "credit_inflow_90d", "active_days_90d", "balance_avg_30d"):
        value, baseline = profile.get(key), overall.get(key)
        if value is None or baseline is None:
            continue
        if baseline > 0 and value >= baseline * 1.25:
            signals.append((key, "above"))
        elif baseline > 0 and value <= baseline * 0.75:
            signals.append((key, "below"))
    above = {k for k, direction in signals if direction == "above"}
    below = {k for k, direction in signals if direction == "below"}
    if "frequency_30d" in above and "monetary_spend_90d" in above:
        name, summary = "Highly active, higher spend", "Activity and recent debit-spend measures are materially above the portfolio median."
    elif "frequency_30d" in above:
        name, summary = "Frequent transactors", "Transaction frequency is above the portfolio median; spend and balances should be considered separately."
    elif "balance_avg_30d" in above and "frequency_30d" in below:
        name, summary = "Higher-balance, lower activity", "Average balances are elevated while transaction frequency is comparatively low."
    elif "frequency_30d" in below and "active_days_90d" in below:
        name, summary = "Lower observed activity", "Recent transaction frequency and active days are below the portfolio median."
    elif "monetary_spend_90d" in above:
        name, summary = "Higher recent spend", "Recent debit-spend measures are above the portfolio median."
    else:
        name, summary = "Mixed behavioural profile", "No single configured behavioural signal dominates relative to the portfolio median."
    if size / max(total, 1) < 0.02:
        summary += " This is a very small cluster and its profile may be unstable."
    return name, summary, [PROFILE_FEATURES.get(k, k) + (" above" if d == "above" else " below") + " portfolio median" for k, d in signals]

def _verify_profile_artifact_checksum(artifact: bytes, expected_checksum: str | None) -> None:
    """Reject missing or altered private model artifacts before deserialization."""
    if not expected_checksum or sha256(artifact).hexdigest() != expected_checksum:
        raise HTTPException(409, "The registered segmentation artifact failed its integrity check.")


@router.get("/api/v1/model-training/development-segmentation/profile")
def development_segmentation_profile(x_api_key: str | None = Header(default=None)):
    """Return aggregate-only interpretation of the latest mock segmentation run."""
    _authorize(x_api_key)
    try:
        db = _database()
        versions = (db.table("model_versions").select("model_version_id,training_dataset_id,artifact_uri,artifact_checksum,algorithm,approval_status,is_active,trained_at,validation_metrics,code_commit_sha")
            .eq("algorithm", "kmeans").eq("approval_status", "experimental")
            .order("trained_at", desc=True).limit(20).execute().data or [])
        version = next((v for v in versions if v.get("training_dataset_id") and str(v.get("artifact_uri", "")).startswith("supabase://")), None)
        if not version:
            raise HTTPException(404, "No development segmentation model is registered.")
        dataset_rows = (db.table("model_datasets").select("dataset_id,data_origin,feature_schema_version,feature_columns,row_count,manifest")
            .eq("dataset_id", version["training_dataset_id"]).limit(1).execute().data or [])
        if not dataset_rows or dataset_rows[0].get("data_origin") != "mock":
            raise HTTPException(409, "The registered segmentation dataset is not explicitly mock-only.")
        dataset = dataset_rows[0]
        artifact_uri = version["artifact_uri"]
        _, remainder = artifact_uri.split("://", 1)
        bucket, path = remainder.split("/", 1)
        artifact = db.storage.from_(bucket).download(path)
        _verify_profile_artifact_checksum(artifact, version.get("artifact_checksum"))
        model = joblib.load(BytesIO(artifact))
        manifest = dataset.get("manifest") or {}
        columns = model.get("feature_columns", [])
        if (manifest.get("purpose") != "development_only_mock_behavioural_segmentation"
                or manifest.get("data_origin") != "mock"
                or manifest.get("production_eligible") is not False
                or model.get("model_purpose") != "development_only_mock_behavioural_segmentation"
                or model.get("production_eligible") is not False
                or model.get("not_a_churn_model") is not True
                or not columns or columns != dataset.get("feature_columns")
                or any(column not in FEATURE_COLUMNS for column in columns)
                or model.get("feature_schema_version") != dataset.get("feature_schema_version")):
            raise HTTPException(409, "The registered artifact does not match the approved mock-only segmentation contract.")
        if not callable(getattr(model.get("estimator"), "predict", None)):
            raise HTTPException(409, "The registered segmentation artifact is missing a valid estimator.")
        customers = _all_rows(db, "customers", "customer_id,data_origin")
        features = _all_rows(db, "customer_features", "customer_id,data_origin,feature_quality_status,feature_as_of," + ",".join(columns))
        frame = prepare_mock_feature_frame(customers, features)
        if frame.empty:
            raise HTTPException(409, "No quality-passed mock feature rows are available for this model.")
        for column in columns:
            if column not in frame:
                frame[column] = np.nan
        labels = model["estimator"].predict(frame[columns])
        profiled = frame[columns].copy()
        profiled["cluster_id"] = labels.astype(int)
        overall = profiled[columns].median(numeric_only=True).to_dict()
        total = len(profiled)
        clusters = []
        for cluster_id, group in profiled.groupby("cluster_id"):
            medians = group[columns].median(numeric_only=True).to_dict()
            size = len(group)
            name, summary, signals = _segment_interpretation(medians, overall, size, total)
            selected = [k for k in ("recency_days", "frequency_30d", "frequency_90d", "monetary_spend_90d", "credit_inflow_90d", "active_days_90d", "balance_avg_30d") if k in columns and pd.notna(medians.get(k))]
            clusters.append({
                "cluster_id": int(cluster_id), "segment_name": name, "customer_count": size,
                "share_pct": round(size / total * 100, 1), "summary": summary,
                "signals": signals,
                "small_cluster_review": size / max(total, 1) < 0.02,
                "feature_medians": {k: round(float(medians[k]), 2) for k in selected},
            })
        return {
            "status": "completed_development_only", "model_version_id": version["model_version_id"],
            "dataset_id": dataset["dataset_id"], "customers_profiled": total,
            "silhouette_score": (version.get("validation_metrics") or {}).get("silhouette_score"),
            "production_eligible": False, "production_approved": False, "not_a_churn_model": True,
            "data_origin": "mock", "clusters": sorted(clusters, key=lambda x: x["cluster_id"]),
            "portfolio_medians": {k: round(float(overall[k]), 2) for k in columns if k in PROFILE_FEATURES and pd.notna(overall.get(k))},
            "interpretation_note": "Names and descriptions are heuristic interpretations of cluster medians versus this mock portfolio; they are not validated customer segments or decision recommendations.",
        }
    except HTTPException:
        raise
    except Exception as exc:
        log.exception("Development segmentation profiling failed")
        raise HTTPException(500, "Unable to profile the development segmentation model; inspect backend logs") from exc


@router.get("/api/v1/model-training/development-segmentation/compare")
def compare_development_segmentation(x_api_key: str | None = Header(default=None)):
    """Read-only repeated-seed comparison of K-means cluster counts on mock data."""
    _authorize(x_api_key)
    try:
        db = _database()
        customers = _all_rows(db, "customers", "customer_id,data_origin")
        features = _all_rows(
            db, "customer_features",
            "customer_id,data_origin,feature_quality_status,feature_as_of," + ",".join(FEATURE_COLUMNS),
        )
        frame = prepare_mock_feature_frame(customers, features)
        if len(frame) < 30:
            raise HTTPException(409, "At least 30 quality-passed mock customer feature rows are required.")
        columns = [column for column in FEATURE_COLUMNS if column in frame and frame[column].notna().any()]
        if len(columns) < 2:
            raise HTTPException(409, "At least two populated behavioural features are required.")
        x = frame[columns]
        seeds = [7, 21, 42, 84, 126]
        comparisons = []
        for k in (2, 3, 4, 5):
            if k >= len(frame):
                continue
            assignments = []
            silhouettes = []
            counts_by_seed = []
            representative_medians = {}
            for seed in seeds:
                estimator = Pipeline([
                    ("imputer", SimpleImputer(strategy="median", add_indicator=True)),
                    ("scaler", StandardScaler()),
                    ("clusterer", KMeans(n_clusters=k, random_state=seed, n_init=20)),
                ])
                labels = estimator.fit_predict(x)
                assignments.append(labels)
                transformed = estimator[:-1].transform(x)
                if 1 < len(np.unique(labels)) < len(frame):
                    silhouettes.append(float(silhouette_score(transformed, labels)))
                counts = np.bincount(labels, minlength=k)
                counts_by_seed.append(counts)
                if seed == 42:
                    profiled = x.copy()
                    profiled["cluster_id"] = labels
                    representative_medians = {
                        str(int(cluster_id)): {
                            column: round(float(value), 2)
                            for column, value in group[columns].median(numeric_only=True).items()
                            if pd.notna(value)
                        }
                        for cluster_id, group in profiled.groupby("cluster_id")
                    }
            stability = [
                float(adjusted_rand_score(assignments[i], assignments[j]))
                for i in range(len(assignments)) for j in range(i + 1, len(assignments))
            ]
            representative_counts = counts_by_seed[seeds.index(42)]
            min_cluster = int(representative_counts.min())
            comparisons.append({
                "cluster_count": k,
                "silhouette_mean": round(float(np.mean(silhouettes)), 4) if silhouettes else None,
                "silhouette_std": round(float(np.std(silhouettes)), 4) if silhouettes else None,
                "stability_ari_mean": round(float(np.mean(stability)), 4) if stability else None,
                "stability_ari_min": round(float(np.min(stability)), 4) if stability else None,
                "representative_seed": 42,
                "representative_cluster_sizes": [int(value) for value in representative_counts],
                "smallest_cluster_share_pct": round(min_cluster / len(frame) * 100, 2),
                "clusters_below_2pct": int(sum(value / len(frame) < 0.02 for value in representative_counts)),
                "feature_medians_by_cluster": representative_medians,
            })
        return {
            "status": "completed_read_only_development_comparison",
            "data_origin": "mock",
            "customers_evaluated": len(frame),
            "features_used": columns,
            "random_seeds": seeds,
            "comparison": comparisons,
            "production_eligible": False,
            "production_approved": False,
            "not_a_churn_model": True,
            "interpretation_note": (
                "Silhouette measures cluster separation, not predictive accuracy. "
                "Mean pairwise adjusted Rand index (ARI) measures agreement across random seeds; "
                "it does not establish business validity. Counts and medians use seed 42. "
                "All comparisons use the same mock snapshot and preprocessing; no records or model registry entries are written."
            ),
        }
    except HTTPException:
        raise
    except Exception as exc:
        log.exception("Development segmentation comparison failed")
        raise HTTPException(500, "Unable to compare development segmentation candidates; inspect backend logs") from exc
