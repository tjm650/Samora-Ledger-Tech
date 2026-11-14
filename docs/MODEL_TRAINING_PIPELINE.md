# Model Training and Evaluation Pipeline

## Scope and safety
The training service is an experimental supervised-learning pipeline. It does not train on mock, synthetic, test, mixed, or unclassified records. It requires imported customers, imported customer feature rows marked `passed`, and imported churn outcomes with `label_confidence='verified'` and a non-null `verified_at`. Features must be calculated no later than the start of the outcome observation window.

The first supported target is churn classification (`churned` versus `retained`). `reactivated` and `unknown` outcomes are excluded. No labels are inferred or manufactured. The pipeline does not alter source records, feature rows, labels, or mock data.

## Endpoints
- `GET /api/v1/model-training/readiness`: read-only aggregate eligibility check.
- `POST /api/v1/model-training/churn`: trains an experimental churn model only when all gates pass.

Both endpoints require `X-API-Key`. The training endpoint requires:
- `MODEL_ARTIFACT_BUCKET`: an existing private Supabase Storage bucket accessible to the backend service role.
- `GIT_COMMIT_SHA`: deployed source commit for lineage.
- Existing `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, and `API_KEY`.

The storage bucket must not be public. Artifacts are written under `experimental/churn/`. Configure lifecycle/retention and access controls through Supabase Storage before enabling training.

## Dataset construction
- Joins imported customers, imported feature rows and verified imported outcomes.
- Uses the latest eligible verified binary outcome per customer.
- Requires a feature cutoff at or before `outcome_window_start` to reduce temporal leakage.
- Uses only numeric behavioural features from `customer-behaviour-v2`.
- Excludes customer identifiers and outcome dates from model inputs.
- Stores aggregate-only dataset manifests and SHA-256 checksums.

## Splitting and model comparison
Rows are ordered by outcome date and split 70% train, 15% validation and 15% test. The validation set selects between:
- class-weighted logistic regression
- class-weighted random forest

The test split remains untouched for final holdout reporting. Metrics include PR-AUC, ROC-AUC, accuracy, precision, recall, Brier score, class balance and confusion matrix.

## Registry and approval
The selected model is registered with `approval_status='experimental'`, `is_active=false`, artifact checksum, dataset reference, feature schema, training commit and validation metrics. Train, validation and test evaluations are recorded separately. The pipeline never approves or activates a model automatically.

A human review and documented acceptance criteria are required before production promotion. A completed experimental training run is not a production performance claim.

## Current limitation
The existing connected database currently contains mock-only customers, transactions and customer features, with no verified churn outcomes. Therefore readiness must remain blocked until approved BancABC data and verified outcomes have been supplied. The implementation can be deployed and tested for readiness without performing model training.
