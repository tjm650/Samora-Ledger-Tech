"""Point-in-time customer feature engineering and data-quality gates.

This module deliberately separates feature calculation from model training.
All windows are anchored to an explicit UTC cutoff; future-dated transactions
are excluded rather than allowed to create negative recency.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any
import logging
import os
import time

import numpy as np
import pandas as pd
from fastapi import APIRouter, Header, HTTPException

log = logging.getLogger("samora.features")
router = APIRouter(tags=["model-data"])

FEATURE_ENGINE_VERSION = "features-v2.0"
FEATURE_SCHEMA_VERSION = "customer-behaviour-v2"
PAGE_SIZE = 1000
BATCH_SIZE = 250


def _utc(value: datetime | str | None = None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    stamp = pd.Timestamp(value)
    if stamp.tzinfo is None:
        stamp = stamp.tz_localize("UTC")
    return stamp.tz_convert("UTC").to_pydatetime()


def calculate_customer_features(
    transactions: pd.DataFrame,
    customer_ids: list[str],
    product_counts: dict[str, int] | None = None,
    as_of: datetime | str | None = None,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Calculate leakage-safe behavioural features at a fixed UTC cutoff."""
    cutoff = pd.Timestamp(_utc(as_of))
    product_counts = product_counts or {}
    tx = transactions.copy()
    quality = {
        "input_rows": int(len(tx)),
        "future_transactions_excluded": 0,
        "invalid_timestamps_excluded": 0,
        "non_posted_transactions_excluded": 0,
        "unknown_customer_transactions": 0,
    }
    if tx.empty:
        tx = pd.DataFrame(columns=[
            "customer_id", "timestamp", "amount", "transaction_type",
            "merchant_category", "channel", "post_transaction_balance",
            "transaction_status",
        ])
    if "timestamp" in tx:
        parsed = pd.to_datetime(tx["timestamp"], utc=True, errors="coerce")
        quality["invalid_timestamps_excluded"] = int(parsed.isna().sum())
        tx = tx.loc[parsed.notna()].copy()
        tx["timestamp"] = parsed.loc[parsed.notna()]
        future_mask = tx["timestamp"] > cutoff
        quality["future_transactions_excluded"] = int(future_mask.sum())
        tx = tx.loc[~future_mask].copy()
    else:
        tx = tx.iloc[0:0].copy()
    if "transaction_status" in tx:
        posted = tx["transaction_status"].fillna("posted").str.lower().isin(
            {"posted", "settled", "completed"}
        )
        quality["non_posted_transactions_excluded"] = int((~posted).sum())
        tx = tx.loc[posted].copy()
    if "amount" not in tx:
        tx["amount"] = 0
    tx["amount"] = pd.to_numeric(tx["amount"], errors="coerce")
    tx = tx.loc[tx["amount"].notna() & (tx["amount"] >= 0)].copy()
    if "post_transaction_balance" not in tx:
        tx["post_transaction_balance"] = np.nan
    tx["post_transaction_balance"] = pd.to_numeric(
        tx["post_transaction_balance"], errors="coerce"
    )
    for col in ("transaction_type", "merchant_category", "channel"):
        if col not in tx:
            tx[col] = None

    known = set(customer_ids)
    quality["unknown_customer_transactions"] = int(
        (~tx["customer_id"].astype(str).isin(known)).sum()
    )
    tx = tx.loc[tx["customer_id"].astype(str).isin(known)].copy()
    grouped = {
        str(cid): group.sort_values("timestamp")
        for cid, group in tx.groupby(tx["customer_id"].astype(str), sort=False)
    }
    rows: list[dict[str, Any]] = []

    for customer_id in customer_ids:
        group = grouped.get(str(customer_id))
        if group is None:
            group = tx.iloc[0:0]
        windows = {
            days: group.loc[group["timestamp"] >= cutoff - pd.Timedelta(days=days)]
            for days in (7, 30, 60, 90, 180)
        }
        w7, w30, w60, w90, w180 = (windows[d] for d in (7, 30, 60, 90, 180))
        debit30 = w30.loc[w30["transaction_type"].eq("Debit")]
        debit60 = w60.loc[w60["transaction_type"].eq("Debit")]
        debit90 = w90.loc[w90["transaction_type"].eq("Debit")]
        debit180 = w180.loc[w180["transaction_type"].eq("Debit")]
        credit30 = w30.loc[w30["transaction_type"].eq("Credit")]
        credit90 = w90.loc[w90["transaction_type"].eq("Credit")]
        salary180 = w180.loc[
            w180["transaction_type"].eq("Credit")
            & w180["merchant_category"].eq("Salary")
        ]
        salary90 = w90.loc[
            w90["transaction_type"].eq("Credit")
            & w90["merchant_category"].eq("Salary")
        ]
        last_tx = group["timestamp"].max() if not group.empty else pd.NaT
        recency = (
            max(0, int((cutoff - last_tx).total_seconds() // 86400))
            if pd.notna(last_tx) else None
        )
        last_salary = salary180["timestamp"].max() if not salary180.empty else pd.NaT
        salary_disruption = bool(
            len(salary180) >= 2
            and pd.notna(last_salary)
            and (cutoff - last_salary).days > 35
        )
        balances30 = w30["post_transaction_balance"].dropna()
        balances180 = w180["post_transaction_balance"].dropna()
        balance_average = (
            float(balances30.mean()) if not balances30.empty
            else (float(balances180.iloc[-1]) if not balances180.empty else None)
        )
        latest_balance = (
            float(balances180.iloc[-1]) if not balances180.empty else None
        )
        peak_balance = (
            float(balances180.max()) if not balances180.empty else None
        )
        drawdown = (
            max(0.0, (peak_balance - latest_balance) / peak_balance)
            if peak_balance is not None and latest_balance is not None and peak_balance > 0
            else 0.0 if peak_balance == 0 else None
        )
        debit_total90 = float(debit90["amount"].sum())
        discretionary90 = float(
            debit90.loc[debit90["merchant_category"].isin(["Travel", "Luxury"]), "amount"].sum()
        )
        count30, count90 = len(w30), len(w90)
        velocity = float(count30 / max(count90 / 3, 1))
        avg_tx = float(w90["amount"].mean()) if not w90.empty else None
        feature_status = "passed" if not group.empty else "insufficient_history"
        row = {
            "customer_id": str(customer_id),
            "recency_days": recency,
            "frequency_7d": int(len(w7)),
            "frequency_30d": int(count30),
            "frequency_90d": int(count90),
            "frequency_180d": int(len(w180)),
            "monetary_spend_30d": round(float(debit30["amount"].sum()), 4),
            "monetary_spend_60d": round(float(debit60["amount"].sum()), 4),
            "monetary_spend_90d": round(debit_total90, 4),
            "monetary_spend_180d": round(float(debit180["amount"].sum()), 4),
            "credit_inflow_30d": round(float(credit30["amount"].sum()), 4),
            "credit_inflow_90d": round(float(credit90["amount"].sum()), 4),
            "debit_outflow_30d": round(float(debit30["amount"].sum()), 4),
            "debit_outflow_90d": round(debit_total90, 4),
            "average_transaction_value_90d": round(avg_tx, 4) if avg_tx is not None else None,
            "transaction_count_90d": int(count90),
            "active_days_90d": int(w90["timestamp"].dt.date.nunique()),
            "channel_diversity_90d": int(w90["channel"].dropna().nunique()),
            "category_diversity_90d": int(w90["merchant_category"].dropna().nunique()),
            "salary_inflow_90d": round(float(salary90["amount"].sum()), 4),
            "product_count": int(product_counts.get(str(customer_id), 0)),
            "balance_avg_30d": round(balance_average, 4) if balance_average is not None else None,
            "velocity_score": round(velocity, 5),
            "discretionary_spend_ratio": round(discretionary90 / debit_total90, 5) if debit_total90 else 0.0,
            "salary_disruption_flag": salary_disruption,
            "balance_drawdown_pct": round(drawdown, 5) if drawdown is not None else None,
            "behavior_segment": (
                "salary_disrupted" if salary_disruption
                else "engaged" if count30 >= 8
                else "low_engagement"
            ),
            "feature_engine_version": FEATURE_ENGINE_VERSION,
            "feature_as_of": cutoff.isoformat(),
            "feature_quality_status": feature_status,
        }
        rows.append(row)
    return rows, quality


def run_feature_pipeline(as_of: datetime | str | None = None) -> dict[str, Any]:
    """Load source data, run checks, persist current features and immutable snapshots."""
    from supabase import create_client

    started = time.monotonic()
    cutoff = _utc(as_of)
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required")
    db = create_client(url, key)

    customers: list[dict[str, Any]] = []
    offset = 0
    while True:
        page = (
            db.table("customers").select("customer_id,data_origin,source_system,import_batch_id")
            .order("customer_id").range(offset, offset + PAGE_SIZE - 1).execute().data or []
        )
        customers.extend(page)
        if len(page) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
    customer_ids = [str(row["customer_id"]) for row in customers]
    if not customer_ids:
        return {"status": "blocked", "reason": "No customer records found", "customers_processed": 0}

    transactions: list[dict[str, Any]] = []
    for start in range(0, len(customer_ids), 50):
        ids = customer_ids[start:start + 50]
        offset = 0
        while True:
            page = (
                db.table("transactions")
                .select("customer_id,timestamp,amount,transaction_type,merchant_category,channel,post_transaction_balance,transaction_status")
                .in_("customer_id", ids).order("timestamp")
                .range(offset, offset + PAGE_SIZE - 1).execute().data or []
            )
            transactions.extend(page)
            if len(page) < PAGE_SIZE:
                break
            offset += PAGE_SIZE

    product_counts: Counter[str] = Counter()
    offset = 0
    while True:
        page = (
            db.table("customer_products").select("customer_id,status")
            .eq("status", "active").order("customer_id")
            .range(offset, offset + PAGE_SIZE - 1).execute().data or []
        )
        for row in page:
            product_counts[str(row["customer_id"])] += 1
        if len(page) < PAGE_SIZE:
            break
        offset += PAGE_SIZE

    frame = pd.DataFrame(transactions)
    feature_rows, calculation_quality = calculate_customer_features(
        frame, customer_ids, dict(product_counts), cutoff
    )

    origins = Counter(str(row.get("data_origin") or "unknown") for row in customers)
    source_counts = Counter(str(row.get("source_system") or "unspecified") for row in customers)
    invalid_customer_count = sum(1 for row in customers if not row.get("customer_id"))
    issue_specs: list[dict[str, Any]] = []
    if calculation_quality["future_transactions_excluded"]:
        issue_specs.append({
            "rule_code": "FUTURE_DATED_TRANSACTIONS", "severity": "warning",
            "affected_rows": calculation_quality["future_transactions_excluded"],
            "description": "Transactions after the feature cutoff were excluded from feature calculations.",
            "remediation": "Check source-system timezone and posting timestamps.",
        })
    if calculation_quality["invalid_timestamps_excluded"]:
        issue_specs.append({
            "rule_code": "INVALID_TRANSACTION_TIMESTAMP", "severity": "error",
            "affected_rows": calculation_quality["invalid_timestamps_excluded"],
            "description": "Transactions with invalid timestamps were excluded.",
            "remediation": "Repair source timestamps before using this data for training.",
        })
    if calculation_quality["non_posted_transactions_excluded"]:
        issue_specs.append({
            "rule_code": "NON_POSTED_TRANSACTIONS", "severity": "info",
            "affected_rows": calculation_quality["non_posted_transactions_excluded"],
            "description": "Pending, reversed or otherwise non-posted transactions were excluded.",
            "remediation": "Confirm source transaction status mapping.",
        })
    if calculation_quality["unknown_customer_transactions"]:
        issue_specs.append({
            "rule_code": "ORPHAN_TRANSACTION_CUSTOMER", "severity": "error",
            "affected_rows": calculation_quality["unknown_customer_transactions"],
            "description": "Transactions reference customers absent from the customer source table.",
            "remediation": "Resolve customer keys or quarantine orphan transactions.",
        })
    if origins.get("mock", 0) or origins.get("synthetic", 0) or origins.get("test", 0):
        issue_specs.append({
            "rule_code": "NON_PRODUCTION_DATA_ORIGIN", "severity": "warning",
            "affected_rows": sum(origins.values()) - origins.get("imported", 0),
            "description": "The customer dataset contains mock, synthetic, test or unclassified source records.",
            "remediation": "Use only approved imported data for production model training and performance claims.",
        })
    if invalid_customer_count:
        issue_specs.append({
            "rule_code": "MISSING_CUSTOMER_KEY", "severity": "error",
            "affected_rows": invalid_customer_count,
            "description": "Customer rows are missing a primary identifier.",
            "remediation": "Repair customer identifiers before feature generation.",
        })

    error_count = sum(x["severity"] == "error" for x in issue_specs)
    warning_count = sum(x["severity"] == "warning" for x in issue_specs)
    quality_status = "failed" if error_count else "warning" if warning_count else "passed"
    quality_summary = {
        "customer_count": len(customers),
        "transaction_count": len(transactions),
        "data_origin_counts": dict(origins),
        "source_system_counts": dict(source_counts),
        "calculation_quality": calculation_quality,
        "feature_engine_version": FEATURE_ENGINE_VERSION,
        "feature_cutoff": cutoff.isoformat(),
        "production_training_eligible": bool(origins) and set(origins) == {"imported"} and error_count == 0,
    }
    quality_run = db.table("data_quality_runs").insert({
        "dataset_name": "customer_behaviour_features",
        "check_suite_version": FEATURE_ENGINE_VERSION,
        "status": quality_status,
        "rows_checked": len(customers) + len(transactions),
        "issue_count": len(issue_specs),
        "error_count": error_count,
        "warning_count": warning_count,
        "summary": quality_summary,
        "execution_ms": int((time.monotonic() - started) * 1000),
    }).execute().data or []
    quality_run_id = quality_run[0]["quality_run_id"] if quality_run else None
    if quality_run_id and issue_specs:
        issue_rows = [{
            "quality_run_id": quality_run_id,
            "dataset_name": "customer_behaviour_features",
            **issue,
        } for issue in issue_specs]
        db.table("data_quality_issues").insert(issue_rows).execute()

    run = db.table("model_runs").insert({
        "status": "running",
        "run_type": "feature_engineering",
        "customers_evaluated": len(customers),
        "records_skipped": 0,
        "records_failed": 0,
        "started_at": cutoff.isoformat(),
        "data_cutoff_at": cutoff.isoformat(),
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "environment_name": os.getenv("APP_ENV", "production"),
        "warnings": [x["rule_code"] for x in issue_specs if x["severity"] == "warning"],
        "run_metadata": {"quality_run_id": quality_run_id, "engine": FEATURE_ENGINE_VERSION},
    }).execute().data or []
    model_run_id = run[0]["model_run_id"] if run else None

    history_fields = [
        "recency_days", "frequency_7d", "frequency_30d", "frequency_90d",
        "frequency_180d", "monetary_spend_30d", "monetary_spend_60d",
        "monetary_spend_90d", "monetary_spend_180d", "credit_inflow_30d",
        "credit_inflow_90d", "debit_outflow_30d", "debit_outflow_90d",
        "average_transaction_value_90d", "transaction_count_90d",
        "active_days_90d", "channel_diversity_90d", "category_diversity_90d",
        "salary_inflow_90d", "product_count", "balance_avg_30d",
        "velocity_score", "discretionary_spend_ratio", "salary_disruption_flag",
        "balance_drawdown_pct", "behavior_segment",
    ]
    history_rows = []
    for feature in feature_rows:
        history_rows.append({
            "customer_id": feature["customer_id"],
            "calculated_at": cutoff.isoformat(),
            "source_data_cutoff": cutoff.isoformat(),
            "feature_engine_version": FEATURE_ENGINE_VERSION,
            "feature_quality_status": feature["feature_quality_status"],
            **{key: feature.get(key) for key in history_fields},
            "feature_values": {key: feature.get(key) for key in history_fields},
        })
    try:
        for start in range(0, len(feature_rows), BATCH_SIZE):
            batch = feature_rows[start:start + BATCH_SIZE]
            db.table("customer_features").upsert(
                [{**row, "updated_at": cutoff.isoformat()} for row in batch],
                on_conflict="customer_id",
            ).execute()
            db.table("customer_feature_history").insert(
                history_rows[start:start + BATCH_SIZE]
            ).execute()
        duration = int((time.monotonic() - started) * 1000)
        if model_run_id:
            db.table("model_runs").update({
                "status": "completed",
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "execution_duration_ms": duration,
                "metrics": {
                    "features_written": len(feature_rows),
                    "quality_status": quality_status,
                    "production_training_eligible": quality_summary["production_training_eligible"],
                },
            }).eq("model_run_id", model_run_id).execute()
    except Exception as exc:
        if model_run_id:
            db.table("model_runs").update({
                "status": "failed",
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "error_summary": str(exc)[:1000],
            }).eq("model_run_id", model_run_id).execute()
        raise

    return {
        "status": "completed" if not error_count else "completed_with_data_errors",
        "customers_processed": len(feature_rows),
        "transaction_rows_read": len(transactions),
        "feature_snapshots_written": len(history_rows),
        "feature_engine_version": FEATURE_ENGINE_VERSION,
        "feature_cutoff": cutoff.isoformat(),
        "data_quality": {
            "quality_run_id": quality_run_id,
            "status": quality_status,
            "errors": error_count,
            "warnings": warning_count,
            "issues": issue_specs,
        },
        "production_training_eligible": quality_summary["production_training_eligible"],
        "model_run_id": model_run_id,
        "execution_duration_ms": int((time.monotonic() - started) * 1000),
    }


@router.post("/api/v1/model-data/features/rebuild")
def rebuild_customer_features(x_api_key: str | None = Header(default=None)):
    expected = os.getenv("API_KEY")
    if not expected:
        raise HTTPException(503, "API_KEY is not configured")
    import secrets
    if not x_api_key or not secrets.compare_digest(x_api_key, expected):
        raise HTTPException(401, "Invalid API key")
    try:
        return run_feature_pipeline()
    except HTTPException:
        raise
    except Exception as exc:
        log.exception("Customer feature engineering pipeline failed")
        raise HTTPException(500, "Feature engineering failed; inspect backend logs") from exc
