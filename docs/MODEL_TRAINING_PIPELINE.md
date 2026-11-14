# Model Training and Evaluation Pipeline

## Production supervised churn pipeline
The production churn trainer remains restricted to imported customers, imported customer feature rows marked `passed`, and imported churn outcomes with `label_confidence='verified'` and a non-null `verified_at`. Features must be calculated no later than the start of the outcome observation window.

The first supported production target is churn classification (`churned` versus `retained`). `reactivated` and `unknown` outcomes are excluded. No production labels are inferred or manufactured. The pipeline does not alter source records, feature rows, labels, or mock data.

## Development-only mock segmentation
- `POST /api/v1/model-training/development-segmentation` runs an isolated unsupervised K-means experiment using only customers with `data_origin='mock'` and feature rows with `data_origin='mock'` and `feature_quality_status='passed'`.
- It does not create churn labels, infer churn, calculate churn probabilities, or write to customer/outcome tables.
- It persists a dataset manifest, experimental model registry entry, training run, evaluation summary, and model artifact in the private artifact bucket.
- The registry entry is `approval_status='experimental'` and `is_active=false`; it is never activated automatically.
- Results are explicitly marked `production_eligible=false` and must not be used for customer-level decisions, marketing, credit, or risk decisions.
- The silhouette score is an unsupervised cluster-cohesion diagnostic, not predictive accuracy.

Both development and production training endpoints require `X-API-Key`, Supabase service-role credentials, and `MODEL_ARTIFACT_BUCKET` pointing to a private Supabase Storage bucket. A deployed source commit is required for lineage.

## Production endpoints
- `GET /api/v1/model-training/readiness`: read-only aggregate eligibility check.
- `POST /api/v1/model-training/churn`: supervised experimental churn model, only when all verified-import gates pass.
- `POST /api/v1/model-training/development-segmentation`: mock-only unsupervised segmentation experiment.

## Production churn dataset construction
- Joins imported customers, imported feature rows and verified imported outcomes.
- Uses the latest eligible verified binary outcome per customer.
- Requires a feature cutoff at or before `outcome_window_start` to reduce temporal leakage.
- Uses numeric behavioural features from `customer-behaviour-v2`.
- Excludes customer identifiers and outcome dates from model inputs.
- Stores aggregate-only dataset manifests and SHA-256 checksums.

## Production churn splitting and comparison
Rows are ordered by outcome date and split 70% train, 15% validation and 15% test. Validation selects between class-weighted logistic regression and random forest. The test split remains untouched for final holdout reporting. Metrics include PR-AUC, ROC-AUC, accuracy, precision, recall, Brier score, class balance and confusion matrix.

## Registry and approval
All models are registered as `experimental` and `is_active=false`. A human review and documented acceptance criteria are required before production promotion. A completed experimental run is not a production performance claim.

## Current limitation
The connected database has mock-only customer and feature rows and no verified churn outcomes. The development segmentation experiment can exercise model artifact storage and registry/evaluation plumbing, but supervised churn training remains blocked until approved BancABC data and verified outcomes are available.
