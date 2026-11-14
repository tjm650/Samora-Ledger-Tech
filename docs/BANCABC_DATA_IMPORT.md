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

Dry-run (validates files and reports row counts/checksum; performs no database writes):

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

The script validates all CSV rows before opening a database write. It then checks existing email collisions, creates a \`data_import_batches\` record, and upserts customers and transactions in batches of 250. A successful import marks the batch \`loaded\`; an interrupted import records \`partially_loaded\` or \`failed\` with counts and an error summary.

The import is idempotent by deterministic primary keys, but the batch itself is an execution record. If a batch is interrupted, inspect the batch and row lineage before retrying. Do not delete a partially loaded batch without a data-owner-approved recovery plan.

The current implementation uses the Supabase REST API in chunks, not a single cross-table database transaction. A failed batch may therefore contain committed chunks; the batch status and \`import_batch_id\` are the recovery boundary. Re-running the same source keys will upsert the same records and attach them to the new batch, so review lineage carefully before retrying.

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
