# Model Data Foundation

This document describes the database foundation for reproducible analytics and machine-learning workflows.

## Scope

The schema supports six model workstreams: churn risk, behavioural segmentation, customer value/CLV, cross-sell propensity, upsell propensity, and transaction anomaly detection. It does not claim that any model has been trained or validated.

## New operational tables

| Table | Purpose |
|---|---|
| `data_import_batches` | Source file/system provenance, checksums, row counts, currency, schema version and import status |
| `data_quality_runs` | Versioned quality-check executions and pass/warn/fail summaries |
| `data_quality_issues` | Rule-level issues, severity, affected row counts and remediation |
| `feature_definitions` | Versioned feature dictionary and calculation contracts |
| `model_datasets` | Immutable dataset manifests, label windows, feature schema, origin, split strategy and checksum |
| `model_evaluations` | Train/validation/test/out-of-time metrics, calibration, confusion matrix and acceptance review |
| `model_predictions` | Versioned customer predictions, model/run/snapshot references and explanation payloads |
| `model_monitoring_metrics` | Feature/prediction drift, performance, data-quality, operational and business-outcome monitoring |

## Existing tables extended

- `customers`: external source reference, customer type, relationship start date, branch/region and source/import lineage.
- `transactions`: external transaction reference, account reference, ISO currency code, posting status, value date, counterparty category and source/import lineage.
- `customer_features` and `customer_feature_history`: additional 7/90/180-day activity, spend, inflow/outflow, activity-day, channel/category-diversity and product-count fields, plus feature version, cutoff and quality status.
- `model_versions`: algorithm/task/target, hyperparameters, dataset and artifact references, checksums, validation metrics, approval lifecycle and source commit.
- `model_runs`: run type, dataset, data cutoff, feature schema, source commit, environment and warnings.
- `customer_churn_outcomes`: outcome observation window, label definition version, confidence, verification timestamp and origin.
- `recommendation_outcomes`: exposure/conversion timestamps, revenue/currency, campaign reference and origin.
- `product_recommendations`: model/run/feature-snapshot lineage, eligibility and suitability state, source type and explanation.

## Security

New operational tables have RLS enabled. Direct `anon` and `authenticated` table privileges are revoked; the backend `service_role` is granted access. These records are server-side model governance and should not be queried directly from browser clients. Expose selected, aggregate views through backend APIs when required.

## Feature contract

Sixteen initial feature definitions have been seeded. They describe the intended calculation, lookback window, source tables, null policy and version. The definitions are metadata, not a claim that the current feature values have already been recomputed. Feature calculations must use a consistent point-in-time cutoff and posted/eligible transactions.

## Important data-quality gate

At schema rollout, the connected dataset was still entirely synthetic/mock: 1,000 customers had `data_origin='mock'`, with no imported customer records and no verified churn outcome labels. The current feature table also had 384 negative `recency_days` values, all 1,000 rows lacked a feature cutoff timestamp, and all 1,000 feature rows were marked unverified after the new status field was added.

Do not train or report production model performance from these records. First repair the feature calculations, run data-quality checks, and obtain verified outcomes. Synthetic data can be used for pipeline smoke tests only and must remain clearly labelled.

## Training and validation policy

- Use point-in-time feature snapshots; never allow post-outcome data into training features.
- Use chronological train/validation/test splits and a final out-of-time holdout for temporal prediction tasks.
- Persist dataset manifests and checksums, feature schema versions, code commit SHAs, model artifacts and evaluation metrics.
- Keep experimental models separate from approved/active production versions.
- For churn and propensity models, report class balance, PR-AUC, ROC-AUC, precision/recall at selected operating thresholds and calibration where labels permit.
- For segmentation, record cluster diagnostics, stability and interpretable profiles.
- For customer value/CLV, distinguish proxy value scores from realised contribution margin and future value.
- For anomaly detection, distinguish unusual behaviour from confirmed fraud.
- Monitor feature drift, score drift, delayed outcomes, recommendation conversion, data quality and execution failures.

## Migrations

- `20261114130000_model_data_foundation.sql`
- `20261114131500_model_data_foundation_fk_indexes.sql`
- `20261114133000_model_feature_contract_and_provenance.sql`
