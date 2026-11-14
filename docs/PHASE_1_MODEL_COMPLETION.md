# Phase 1 — Development Model Completion Record

**Status:** Complete for the agreed mock-data development scope  
**Model:** Customer behavioural segmentation  
**Selected development candidate:** K-means, four clusters, expanded behavioural feature schema  
**Data:** Synthetic/mock only  
**Release state:** Experimental, inactive, not production-approved

## 1. Phase 1 objective

Exercise the end-to-end development workflow for customer-behaviour segmentation using the project's existing mock portfolio. Phase 1 demonstrates data preparation, feature engineering, model training, artifact storage and integrity, aggregate segment profiling, candidate comparison, and a reviewable dashboard.

Phase 1 does not establish that the segments are representative of BancABC customers, predict churn, measure customer lifetime value, or justify customer-level actions.

## 2. Delivered scope

| Workstream | Phase 1 result | Evidence / implementation |
|---|---|---|
| Model data foundation | Versioned dataset, feature, run, evaluation and artifact lineage tables | `docs/MODEL_DATA_FOUNDATION.md`; Supabase model-data migrations |
| Feature engineering | Point-in-time, quality-gated customer behavioural features and feature history | `backend/feature_engineering.py` |
| Derived features | Four additional behavioural signals calculated in memory under a new schema version | `backend/development_model_training.py` |
| Development training | Mock-only K-means training, checksum-protected private artifact, experimental registry entry | `POST /api/v1/model-training/development-segmentation` |
| Segment profiling | Aggregate cluster sizes, shares, medians and heuristic interpretations; no customer assignments exposed | `GET /api/v1/model-training/development-segmentation/profile` |
| Candidate review | k=2–5 comparison and original-versus-expanded feature diagnostics | `GET /api/v1/model-training/development-segmentation/compare` |
| Dashboard | Growth Intelligence segment profiles and comparison view through server-side API proxies | `frontend/app/growth/` |
| Tests and CI | Backend unit tests, Python compilation and frontend type-check in GitHub Actions | `.github/workflows/ci.yml` |
| Source-data controls | Controlled BancABC import contract, dry-run default and explicit approval/reconciliation gates | `backend/bancabc_import.py`; `docs/BANCABC_DATA_IMPORT.md` |
| Supervised training foundation | Leakage-aware, verified-label-only churn pipeline implemented but gated from current mock data | `backend/model_training.py` |

## 3. Selected candidate and evidence

The expanded-feature K-means k=4 model is retained as the Phase 1 development candidate.

Latest recorded training run:

- Model version: `5f459a5a-4cd6-46d5-af5c-656967fd20d6`
- Dataset: `c4e0b35e-1856-433e-b2a4-d54bbadb06e7`
- Customers used: 1,000 quality-passed mock customers
- Training silhouette diagnostic: 0.4878
- Cluster sizes: 300, 500, 37 and 163
- Registry status: experimental; inactive
- Production approved / eligible: false

The same-snapshot comparison reported for expanded features:

| Cluster count | Mean silhouette | Pairwise seed ARI mean | Smallest cluster share |
|---:|---:|---:|---:|
| 2 | 0.5108 | 1.0000 | 20.0% |
| 3 | 0.4797 | 1.0000 | 20.0% |
| 4 | 0.4917 | 1.0000 | 3.7% |
| 5 | 0.4489 | 0.8672 | 3.7% |

The original base-feature k=4 candidate had a higher silhouette mean (0.5539), but its smallest cluster contained only 7 customers (0.7%). Expanded-feature k=4 is retained as a more balanced candidate for interpretation, not as a statistically or commercially validated winner.

The four aggregate profile labels currently presented are:

| Segment label | Customers | Share |
|---|---:|---:|
| Higher recent spend | 300 | 30.0% |
| Mixed behavioural profile | 500 | 50.0% |
| No recent transactions | 37 | 3.7% |
| Low and declining activity | 163 | 16.3% |

These labels are heuristic summaries of mock-portfolio medians. They are not verified business classifications.

## 4. Model card

### Intended purpose
Explore whether the mock customer portfolio contains interpretable groups based on observed transaction activity and monetary behaviour.

### Intended users
Internal product, analytics and engineering reviewers evaluating the Phase 1 prototype.

### Prohibited uses
- Churn prediction, churn probability or retention-risk ranking.
- Credit, lending, fraud, AML, risk, pricing or eligibility decisions.
- Customer contact, campaign targeting, product offers or relationship-manager prioritisation.
- Claims about actual BancABC customer behaviour or portfolio composition.
- Production deployment, automated decisions or customer-level assignment exposure.

### Data and representativeness
All training data used for this candidate is synthetic/mock. It is not an approved BancABC extract and may not reproduce real customer distributions, transaction patterns, seasonality, channel mix or product holdings.

### Method
K-means clustering with median imputation, missingness indicators and standard scaling. The expanded feature schema derives 90-day net cashflow, 90-day debit-to-credit ratio, 30-day spend trend versus the 90-day monthly run rate, and 7-day activity consistency versus the 30-day run rate.

### Evaluation
Silhouette is a geometric cluster-separation diagnostic, not predictive accuracy. Seed-to-seed ARI measures agreement across tested random initialisations on the same snapshot; it is not temporal or population stability. No labelled target exists for this unsupervised task, so classification metrics such as accuracy, precision, recall, ROC-AUC and PR-AUC are not applicable.

### Explainability
The dashboard exposes aggregate cluster sizes, shares, medians and relative signals. It does not expose customer-level assignments. Segment names and descriptions are heuristic and should be checked by a business owner against representative, approved data before any operational use.

### Known limitations
- Mock-only training population.
- No approved source-system export, source-owner approval or reconciliation evidence currently available.
- No independently validated business segment definitions.
- No temporal stability evidence; this is not a blocker for closing the agreed mock-data Phase 1 scope.
- Reconstructed profiles use the current eligible feature snapshot and can differ from training-time assignments if data changes.
- Currency values and source-system semantics have not been validated against approved BancABC extracts.

## 5. Phase 1 acceptance checklist

- [x] Model data schema and lineage foundation implemented.
- [x] Point-in-time feature engineering and quality gates implemented.
- [x] Mock-only training executed and model artifact registered.
- [x] Artifact checksum verified before deserialisation in the profile workflow.
- [x] Candidate cluster counts and feature sets compared.
- [x] Aggregate profiles reviewed and segment labels differentiated.
- [x] Growth Intelligence dashboard surfaces profiles and diagnostics.
- [x] Backend and frontend CI checks pass on the latest verified code state.
- [x] Model remains experimental, inactive and not production-approved.
- [x] Model card and limitations documented.
- [ ] Approved BancABC source data and owner sign-off — explicitly outside mock-data Phase 1 and required before a real-data phase.
- [ ] Business-owner validation on representative customers — cannot be completed with synthetic data.
- [ ] Temporal stability review — optional follow-up, not a Phase 1 completion gate.

## 6. Handoff to the next phase

Phase 1 is complete as a mock-data development and demonstration milestone. The next phase can focus on approved BancABC data onboarding, source reconciliation, business validation of segment definitions and controlled re-evaluation. The current candidate must remain inactive until those gates are satisfied.

The separate supervised churn pipeline must not be treated as trained: the current database has no verified imported churn outcomes, and mock records are excluded by design.
