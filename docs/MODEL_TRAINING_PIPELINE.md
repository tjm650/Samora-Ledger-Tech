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


## Aggregate segment profiling
- `GET /api/v1/model-training/development-segmentation/profile` retrieves the latest registered experimental K-means artifact and reconstructs cluster membership from the current quality-passed mock feature snapshot.
- The endpoint returns aggregate cluster counts, shares, feature medians and heuristic descriptions relative to portfolio medians. It does not return customer identifiers or individual cluster assignments.
- Clusters below 2% of the profiled population are flagged for manual review. Descriptions are heuristic and are not validated business classifications.
- The Growth Intelligence page displays this read-only profile through a server-side API proxy. The proxy uses the server-held API key; no API key is exposed to the browser.
- The profile is a view of the latest registered model against the current eligible mock feature snapshot. If features change after training, reconstructed cluster membership may differ from the original training-time distribution.
- All output remains mock-only, experimental, not a churn model, and not production eligible.


## Read-only segmentation candidate comparison
- `GET /api/v1/model-training/development-segmentation/compare` compares K-means solutions with 2, 3, 4 and 5 clusters on the same current mock feature snapshot.
- Each candidate uses the existing median-imputation, missingness-indicator and standard-scaling pipeline, with five fixed random seeds and 20 K-means initialisations per seed.
- Reports mean and standard deviation of silhouette scores (using a fixed sample of up to 500 rows per seed), mean and minimum pairwise adjusted Rand index (ARI) across seeds, and representative cluster sizes/median features from seed 42.
- Silhouette is a separation diagnostic, not predictive accuracy. ARI is seed-to-seed assignment agreement, not evidence of business validity.
- The endpoint is read-only: it does not upload artifacts, insert datasets, create model versions/runs/evaluations, alter customer records, or activate a candidate.
- The Growth Intelligence comparison request is sequenced after the existing profile request to limit concurrent memory use. The comparison table is mock-only and experimental. Candidate results must be reviewed alongside cluster size, stability and business interpretability; no automatic winner is selected.


## Derived behavioural feature expansion
- Development segmentation now derives four additional signals at read time from the existing quality-passed feature snapshot: 90-day net cashflow, 90-day debit-to-credit ratio, 30-day spend trend versus the 90-day monthly run rate, and 7-day activity consistency versus the 30-day run rate.
- Ratios with zero or missing denominators remain null and are handled by the existing median-imputation pipeline; infinities are converted to null.
- These are derived model-input features, not new source facts or new database columns. The original source features and customer records are unchanged.
- The derived feature schema is versioned as customer-behaviour-v2-derived-1. Existing registered artifacts retain their original schema and must not be silently reinterpreted; a new segmentation training run is required to use the expanded schema.
- This expansion is experimental and mock-only. Feature utility and cluster interpretability must be compared before any production use.
