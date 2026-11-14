# BancABC source-data import runbook

## Purpose and guardrails

Use this process only for an approved BancABC export. The importer is deliberately separate from feature engineering and model training.

- Existing mock/synthetic rows are not deleted or relabelled.
- Imported rows receive \`data_origin=imported\`, a stable \`source_system\`, and an \`import_batch_id\`.
- Stable UUIDv5 identifiers are derived from source-system plus external record reference, making repeat imports idempotent for the same source keys.
- Customer email collisions with a different existing customer ID are rejected before any write. Resolve identity mapping with the data owner; do not merge customers based on names or email guesses.
- Dry-run is the default. \`--apply\` is required to write.
- Use the Supabase service-role key only in a trusted local environment. Never place it in a CSV, command argument, frontend variable, GitHub file, or chat.
- The importer does not create churn labels, infer missing transaction statuses, or train models.

## Required source files

Use the header-only templates in \`docs/templates/\`.

### Customers

Required: \`external_customer_ref\`, \`full_name\`, \`email\`.

Optional: \`account_tier\`, \`customer_type\`, \`relationship_start_date\` (\`YYYY-MM-DD\`), \`branch_code\`, \`region_code\`.

\`external_customer_ref\` must be stable and unique within the source system. Email is required by the current customer table and must not collide with another customer in the database.

### Transactions

Required: \`external_transaction_ref\`, \`external_customer_ref\`, \`timestamp\`, \`amount\`, \`transaction_type\`, \`merchant_category\`, \`channel\`, \`post_transaction_balance\`.

Optional: \`transaction_status\` (defaults to \`posted\` only when omitted), \`account_ref\`, \`currency_code\`, \`value_date\`, \`counterparty_category\`.

- Timestamps must be ISO-8601 and include an explicit timezone.
- Transaction type must be \`Debit\` or \`Credit\`.
- Amount must be non-negative. Balance may be negative where overdrafts are valid.
- Status must be one of \`posted\`, \`settled\`, \`completed\`, \`pending\`, \`reversed\`, \`failed\`.
- Every transaction customer reference must exist in the customer file.
- Currency must be an ISO 4217 three-letter code; the command's currency is the default for rows without one.
- Export the full approved customer identity crosswalk with the transaction extract; never infer customer matches.

## Local execution

From the repository root, install the backend requirements in an isolated environment, then set \`SUPABASE_URL\` and \`SUPABASE_SERVICE_ROLE_KEY\` in that local environment.

Dry-run (validates files and emits aggregate reconciliation, branch/status totals and checksum; performs no database writes):

\`\`\`powershell
python backend/bancabc_import.py \`
  --customers .\\approved\\bancabc_customers.csv \`
  --transactions .\\approved\\bancabc_transactions.csv \`
  --source-system bancabc_core_banking \`
  --currency USD
\`\`\`

Only after the dry-run report and source-owner approval, apply:

\`\`\`powershell
python backend/bancabc_import.py \`
  --customers .\\approved\\bancabc_customers.csv \`
  --transactions .\\approved\\bancabc_transactions.csv \`
  --source-system bancabc_core_banking \`
  --currency USD \`
  --apply
\`\`\`

Use the actual currency agreed with BancABC; USD above is an example, not an assumption.

## Import behavior and recovery

The importer checks existing email collisions and source-key records before creating a `data_import_batches` record. New customer and transaction rows are inserted in chunks of 250. A successful import marks the batch `loaded`; an interrupted import records `partially_loaded` or `failed` when the status update succeeds.

The Supabase REST API writes chunks separately; this is not a single cross-table database transaction. A failed batch may therefore contain committed chunks. Do not delete a partially loaded batch or start a fresh import with the same source keys.

Recovery is explicit:
1. Inspect the original `data_import_batches` row and the `import_batch_id` values on customer and transaction rows.
2. Confirm the original batch is `validating`, `partially_loaded` or `failed`, and that its source system, currency, checksum and approval reference match the exact package.
3. Re-run the same unchanged CSV files and approval manifest with `--resume-batch-id <ORIGINAL_IMPORT_BATCH_UUID> --apply`.
4. The importer refuses recovery if any existing identical row is not linked to that original batch. It inserts only missing rows, verifies the final customer and transaction row counts linked to the original batch, then marks that same batch `loaded`.
5. If a process stopped after a database chunk committed but before its response was received, the next run detects those rows by deterministic ID and confirms their original batch lineage before continuing.

Example recovery command:

```powershell
python backend/bancabc_import.py `
  --customers .\\approved\\bancabc_customers.csv `
  --transactions .\\approved\\bancabc_transactions.csv `
  --source-system bancabc_core_banking `
  --currency USD `
  --approval-manifest .\\approved\\bancabc_approval_manifest.json `
  --resume-batch-id <ORIGINAL_IMPORT_BATCH_UUID> `
  --apply
```

A new import without `--resume-batch-id` is rejected if any identical source records already exist, preventing a second batch from claiming incomplete lineage. If batch state or lineage is ambiguous, stop and investigate manually; do not retry blindly.

## After import

1. Reconcile source totals, inserted/updated counts, duplicate keys, currency, date ranges and per-branch totals with BancABC's signed control totals.
2. Review \`data_import_batches\` and verify every imported customer/transaction has the expected \`source_system\`, \`data_origin\`, and batch ID.
3. Run the feature rebuild endpoint after import.
4. Inspect the data-quality run. Production eligibility requires customer and transaction origins to be exclusively \`imported\` and zero data-quality errors.
5. Define and verify churn outcomes and recommendation exposure/conversion labels before building supervised training datasets.
6. Use chronological splits and a final out-of-time holdout. Do not train on mock rows or mix mock/imported populations in a production dataset.

## Current limitations

This is a controlled CSV ingestion utility, not a direct core-banking connector. It expects an approved, normalized two-file export and does not implement encryption-at-rest for local source files, PII masking, automated SFTP pickup, multi-currency FX normalization, or automatic duplicate-resolution workflows. Keep source files in BancABC-approved secure storage and delete local copies according to the bank's retention policy.


## Phase 2 approval and reconciliation manifest

Any database write now requires a third package file: a JSON approval manifest based on `docs/templates/bancabc_approval_manifest.template.json`. Prepare it from the source owner's approved export specification and control report; never guess or derive approval evidence from the CSV itself.

The manifest must contain:
- Approval reference, named approving data owner and approval timestamp with timezone.
- Stable source-system identifier and confirmed ISO 4217 currency.
- Extraction start/end timestamps with timezone.
- Source customer and transaction row counts.
- Source debit, credit and combined transaction amount control totals.
- SHA-256 checksum matching the exact customer and transaction CSV files supplied to the importer.

The importer compares these values to the normalized CSV files before creating an import batch or writing records. A mismatch rejects the package. The manifest is a consistency gate, not a digital signature: an authorized project reviewer must independently verify the approval reference and control report with the BancABC source owner. A self-authored manifest is not proof of bank approval.

For apply mode, include `--approval-manifest .\\approved\\bancabc_approval_manifest.json` before `--apply`. The checksum is available from dry-run output; put that exact checksum into the manifest after the source files are finalized. Re-run dry-run after any change to either CSV.


## Phase 2 dry-run readiness report

A dry-run emits aggregate reconciliation evidence without writing to Supabase:
- Validated customer and transaction row counts and exact-file SHA-256 checksum.
- Package currency and observed UTC transaction time range.
- Transaction-status counts.
- Debit, credit and combined amount totals.
- Branch-level transaction counts and debit/credit totals, grouped through the supplied customer branch code (missing branch codes are reported as `UNSPECIFIED`).
- Whether the supplied approval manifest passed structural and control-total checks.

Without a manifest, the report is marked `awaiting_approval_manifest`; this is not an import-ready approval. With a manifest, it is marked `approval_manifest_validated`, but independent human verification of the bank's approval and source control report is still mandatory.

The importer currently enforces one package currency per export. Mixed-currency files must be split into separately approved packages; it does not perform FX conversion. Transaction timestamps must fall within the manifest's half-open extraction interval `[extraction_start, extraction_end)`. Approval must predate or equal extraction start.
