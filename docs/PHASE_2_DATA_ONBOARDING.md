# Phase 2 — Mock-Data Platform Readiness (BancABC Onboarding Deferred)

**Status:** In progress — platform readiness using mock data  
**Phase 1:** Closed — mock-data prototype  
**Current delivery mode:** Mock data only; continue platform development, integration testing and operational readiness  
**BancABC onboarding:** Deferred until the platform is ready for live production and the approved source package is supplied  
**Production model state:** No model is approved for production use

## Objective

Make the platform ready for a live-production handover while continuing to use the existing mock dataset. Complete product functionality, API/UI integration, reliability, observability, security and operational checks against mock data. BancABC onboarding is a later release gate: the approved package is expected when the platform is ready for live production, not as a prerequisite for current development.

Do not import or request real BancABC records during this mock-data readiness stage. Keep the import pipeline, approval controls and reconciliation tooling implemented and tested, but dormant. When the production-readiness decision is reached, obtain the bank-approved package and independently verify its source-owner approval and control evidence before any import.

## Current delivery mode — mock data only

- Use only the existing synthetic/mock customer and transaction records for ongoing development and demonstrations.
- Do not block frontend, backend, analytics, model-development or operational-readiness work while waiting for BancABC exports.
- Keep mock provenance explicit in APIs, dashboards, model manifests and reports; never present mock results as actual BancABC performance.
- Keep experimental models inactive and not production-approved. Mock-data model diagnostics are for engineering and demonstration only.
- Do not invoke the importer with `--apply`, create real-data feature snapshots, or mix mock and imported populations.
- Treat the BancABC approval package and first import as a future production-onboarding workstream after the platform readiness review.

## Workstreams and exit criteria

### 2.1 Future production gate — source ownership and export approval

These items are intentionally deferred and do not block current mock-data platform readiness.
- [ ] Named BancABC data owner and authorized approver.
- [ ] Written approval reference covering the exact datasets, purpose, extraction window and permitted use.
- [ ] Stable source-system identifier and documented source-key semantics.
- [ ] Confirmed ISO 4217 currency/currency treatment.
- [ ] Secure transfer and retention procedure agreed.
- [ ] Customer identity crosswalk approved by the data owner.

### 2.2 Future production gate — import contract and provenance

The importer contract is implemented and maintained through tests. Production package validation is deferred until the approved export is supplied.
- [x] Customer and transaction CSV schemas documented.
- [x] Dry-run is default; database writes require explicit `--apply`.
- [x] Deterministic source-key identifiers and explicit imported provenance.
- [x] Approval manifest required for apply mode.
- [x] Manifest counts, debit/credit/combined amount totals, currency, extraction timestamps and exact-file checksum validated before writes.
- [x] Approval evidence and reconciliation values persisted in import-batch metadata.
- [ ] Independent review confirms approval reference and control report with BancABC owner.
- [x] Confirm manifest currency codes against the ISO 4217 reference list rather than a three-letter syntax check alone.
- [ ] Add source-system-specific reconciliation controls where the export provides additional totals (e.g. per branch, account or posting status).

### 2.3 Future production gate — import execution and reconciliation

No import execution is planned during the current mock-data stage.
- [ ] Run dry-run against approved, securely transferred exports.
- [ ] Reconcile row counts, debit/credit totals, currency, date range, branch totals, duplicates and customer references to signed source controls.
- [x] Implement and test idempotency, partial-import recovery, exact batch lineage checks and read-only batch verification before apply.
- [ ] Execute one controlled import with explicit approval.
- [ ] Verify import-batch lineage on every imported customer and transaction.
- [ ] Confirm no mock rows were deleted, relabelled or overwritten.

### 2.4 Current work — mock-data quality and feature readiness

Continue quality checks, feature engineering and diagnostics against the explicitly marked mock dataset. The imported-only checks below are future production gates.
- [ ] Run post-import data-quality checks and resolve all blocking errors.
- [ ] Confirm imported-only population and provenance consistency.
- [ ] Validate timezone, posting status, reversals, transaction types, currency and monetary precision with source owner.
- [ ] Rebuild features from approved imported records using a documented cutoff.
- [ ] Review feature distributions, missingness, negative recency, future-dated rows and outliers.

### 2.5 Current work — product and model readiness on mock data

Continue aggregate profile review, usability validation and model-governance work using mock data. Business validation against BancABC's actual semantics remains a future production gate.
- [ ] BancABC business owners review segment definitions and aggregate profiles.
- [ ] Assess whether feature definitions represent bank-specific product and transaction semantics.
- [ ] Refit segmentation only after data-quality and business review; compare against the mock candidate without carrying over mock interpretations as truth.
- [ ] Keep any real-data model experimental and inactive until independent validation and formal approval.
- [ ] Define verified outcomes before any supervised churn or propensity training.

### 2.6 Current work — deployed API smoke verification

- [x] Add `scripts/mock_data_smoke_test.py`, a standard-library-only, read-only smoke test for backend health, executive overview, executive transactions, Growth Intelligence overview and development segmentation profile.
- [x] Require server-side `SAMORA_API_URL` and `SAMORA_API_KEY`; never print credentials or response bodies.
- [x] Use GET requests only. The script does not seed data, run pipelines, train models, import records or mutate database state.
- [ ] Run the smoke test against the deployed Render backend using trusted local/server environment variables and record the pass/fail summary.
- [ ] Resolve any failed endpoint and rerun the complete check.

Run from the repository root:

```bash
SAMORA_API_URL=https://samora-ledger-analytics-ppsw.onrender.com SAMORA_API_KEY=<server-side-api-key> python scripts/mock_data_smoke_test.py
```

On PowerShell:

```powershell
$env:SAMORA_API_URL = "https://samora-ledger-analytics-ppsw.onrender.com"
$env:SAMORA_API_KEY = "<server-side-api-key>"
python scripts/mock_data_smoke_test.py
```

Do not paste the API key into GitHub, chat, shell history shared with others, or committed files. A successful HTTP response proves endpoint availability and JSON shape only; it does not establish business correctness, complete UI rendering, data quality, or production model approval.

## Import package contract

The controlled package contains:
1. Approved customer CSV.
2. Approved transaction CSV.
3. Approval/reconciliation JSON manifest based on `docs/templates/bancabc_approval_manifest.template.json`.
4. Separately verifiable bank approval/control-total evidence, held in approved secure storage.

The manifest is a consistency mechanism, not a cryptographic signature. It cannot independently prove the identity or authority of its author. A human reviewer must validate the approval evidence with the named source owner.

## Safety and governance rules

- Never commit customer exports, manifests containing sensitive data, credentials or source control reports to Git.
- Never paste customer-level records or secrets into chat.
- Use the Supabase service-role credential only in a trusted local environment.
- Keep dry-run as the default and do not use `--apply` until every source approval and reconciliation gate is complete.
- Do not merge imported and mock populations for production training.
- Do not infer churn labels, customer identity matches, currency conversion or missing transaction statuses.
- Do not expose customer-level segment assignments or use experimental segments for customer contact, credit, fraud, AML, pricing or eligibility decisions.

## Production-onboarding handover gate

The absence of BancABC exports is expected at this stage and is not a blocker to mock-data platform readiness. The approved package will be supplied when the platform is ready for live production. At that point, obtain the actual customer and transaction exports, named source-owner approval, stable source-system identifier, confirmed currency, extraction window and independently verifiable control totals. Run dry-run and read-only reconciliation first. Only proceed to a controlled database import after explicit project authorization and independent approval verification.
