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


## Feature-engineering implementation

The backend now includes `backend/feature_engineering.py` and exposes a protected rebuild endpoint:

`POST /api/v1/model-data/features/rebuild`

Supply the backend `X-API-Key`. The pipeline:
1. Reads customer, posted transaction and active product ownership data.
2. Uses one explicit UTC feature cutoff for every customer and every lookback window.
3. Excludes future-dated and non-posted transactions from feature calculations.
4. Calculates 7/30/60/90/180-day frequency and monetary windows, cash flows, average transaction value, activity days, channel/category diversity, payroll inflows, salary disruption, balances and product counts.
5. Writes the current feature row to `customer_features` and an immutable point-in-time snapshot to `customer_feature_history`.
6. Records data-quality findings in `data_quality_runs` and `data_quality_issues`, and execution metadata in `model_runs`.

The salary-disruption indicator requires a prior payroll pattern (at least two salary credits in the 180-day lookback) and a gap greater than 35 days. This avoids treating a single salary-labelled credit as a reliable payroll baseline.

The pipeline never silently changes the source data or creates churn labels. A dataset containing mock/synthetic/test or unclassified customer origins is flagged as not eligible for production model training. A future-dated transaction is excluded and reported; the feature cutoff is persisted so the same feature state can be reproduced.

Unit tests for cutoff handling, non-posted transaction exclusion, empty customer histories and payroll disruption are in `backend/tests/test_feature_engineering.py`.


## BancABC source-data import readiness

A controlled CSV importer is available in `backend/bancabc_import.py`. Its dry-run mode is the default; writing requires an explicit `--apply` flag and locally supplied Supabase service-role credentials. The importer uses stable source-key-derived UUIDs, strict field validation, exact-match replay checks, customer-email collision checks, chunked writes, and `data_import_batches` lineage. It never deletes or relabels mock records.

See `docs/BANCABC_DATA_IMPORT.md` for the data contract, secure execution instructions, reconciliation steps, recovery behavior and known limitations. Header-only templates are provided under `docs/templates/`. Unit tests are in `backend/tests/test_bancabc_import.py`.

The importer is a controlled normalized-CSV workflow, not a direct core-banking connector. No BancABC data has been imported as part of preparing this tooling. Do not use `--apply` until the data owner approves the extract, identity crosswalk, currency and signed control totals.
