# Phase 2 — BancABC Data Onboarding and Validation

**Status:** In progress  
**Phase 1:** Closed — mock-data prototype  
**Current source-data state:** No approved BancABC exports have been accepted or imported  
**Production model state:** No model is approved for production use

## Objective

Establish a controlled, auditable path for onboarding approved BancABC customer and transaction exports, reconciling them to source-owner control totals, validating provenance and data quality, and only then rebuilding features for business review.

Engineering work may proceed with synthetic fixtures. No real customer data may be imported until the source owner and authorized project reviewer have completed the approval gate.

## Workstreams and exit criteria

### 2.1 Source ownership and export approval
- [ ] Named BancABC data owner and authorized approver.
- [ ] Written approval reference covering the exact datasets, purpose, extraction window and permitted use.
- [ ] Stable source-system identifier and documented source-key semantics.
- [ ] Confirmed ISO 4217 currency/currency treatment.
- [ ] Secure transfer and retention procedure agreed.
- [ ] Customer identity crosswalk approved by the data owner.

### 2.2 Import contract and provenance
- [x] Customer and transaction CSV schemas documented.
- [x] Dry-run is default; database writes require explicit `--apply`.
- [x] Deterministic source-key identifiers and explicit imported provenance.
- [x] Approval manifest required for apply mode.
- [x] Manifest counts, debit/credit/combined amount totals, currency, extraction timestamps and exact-file checksum validated before writes.
- [x] Approval evidence and reconciliation values persisted in import-batch metadata.
- [ ] Independent review confirms approval reference and control report with BancABC owner.
- [x] Confirm manifest currency codes against the ISO 4217 reference list rather than a three-letter syntax check alone.
- [ ] Add source-system-specific reconciliation controls where the export provides additional totals (e.g. per branch, account or posting status).

### 2.3 Import execution and reconciliation
- [ ] Run dry-run against approved, securely transferred exports.
- [ ] Reconcile row counts, debit/credit totals, currency, date range, branch totals, duplicates and customer references to signed source controls.
- [x] Implement and test idempotency, partial-import recovery, exact batch lineage checks and read-only batch verification before apply.
- [ ] Execute one controlled import with explicit approval.
- [ ] Verify import-batch lineage on every imported customer and transaction.
- [ ] Confirm no mock rows were deleted, relabelled or overwritten.

### 2.4 Data quality and feature rebuild
- [ ] Run post-import data-quality checks and resolve all blocking errors.
- [ ] Confirm imported-only population and provenance consistency.
- [ ] Validate timezone, posting status, reversals, transaction types, currency and monetary precision with source owner.
- [ ] Rebuild features from approved imported records using a documented cutoff.
- [ ] Review feature distributions, missingness, negative recency, future-dated rows and outliers.

### 2.5 Business validation and model reassessment
- [ ] BancABC business owners review segment definitions and aggregate profiles.
- [ ] Assess whether feature definitions represent bank-specific product and transaction semantics.
- [ ] Refit segmentation only after data-quality and business review; compare against the mock candidate without carrying over mock interpretations as truth.
- [ ] Keep any real-data model experimental and inactive until independent validation and formal approval.
- [ ] Define verified outcomes before any supervised churn or propensity training.

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

## Current blocker

The repository previously contained only header-only CSV templates, not approved source exports. Therefore Phase 2 can advance through contract hardening and test coverage, but import execution and real-data validation remain blocked until BancABC supplies the approved export package and independently verifiable approval/control evidence.
