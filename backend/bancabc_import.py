"""Controlled, provenance-preserving BancABC CSV importer.

Dry-run is the default. A write requires --apply and backend Supabase service-role
credentials in the local environment. No credentials are read from command-line args.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import sys
import uuid
from collections import Counter
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import pycountry

CUSTOMER_REQUIRED = ("external_customer_ref", "full_name", "email")
TRANSACTION_REQUIRED = (
    "external_transaction_ref", "external_customer_ref", "timestamp", "amount",
    "transaction_type", "merchant_category", "channel", "post_transaction_balance",
)
TRANSACTION_TYPES = {"debit": "Debit", "credit": "Credit"}
TRANSACTION_STATUSES = {"posted", "settled", "completed", "pending", "reversed", "failed"}
SOURCE_RE = re.compile(r"^[a-zA-Z0-9_.-]{2,80}$")
SCHEMA_VERSION = "bancabc-csv-v1"


class ImportValidationError(ValueError):
    pass


def stable_id(source_system: str, entity: str, external_ref: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"samora-ledger:{source_system}:{entity}:{external_ref}"))


def _read_csv(path: str | Path) -> list[dict[str, str]]:
    with open(path, "r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ImportValidationError(f"{path}: CSV has no header row")
        return [{str(k).strip(): (v or "").strip() for k, v in row.items()} for row in reader]


def _required(row: dict[str, str], fields: tuple[str, ...], dataset: str, line: int) -> None:
    missing = [field for field in fields if not row.get(field)]
    if missing:
        raise ImportValidationError(f"{dataset} row {line}: missing required fields: {', '.join(missing)}")


def _iso_timestamp(value: str, dataset: str, line: int) -> str:
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ImportValidationError(f"{dataset} row {line}: timestamp must be ISO-8601") from exc
    if stamp.tzinfo is None:
        raise ImportValidationError(f"{dataset} row {line}: timestamp must include a timezone")
    return stamp.astimezone(timezone.utc).isoformat()


def _decimal(value: str, field: str, dataset: str, line: int, *, allow_negative: bool = False) -> str:
    try:
        amount = Decimal(value)
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ImportValidationError(f"{dataset} row {line}: {field} must be numeric") from exc
    if not amount.is_finite():
        raise ImportValidationError(f"{dataset} row {line}: {field} must be finite")
    if not allow_negative and amount < 0:
        raise ImportValidationError(f"{dataset} row {line}: {field} cannot be negative")
    return format(amount.quantize(Decimal("0.0001")), "f")


def normalize_customer_rows(rows: list[dict[str, str]], source_system: str) -> list[dict[str, Any]]:
    output, seen_refs, seen_emails = [], set(), set()
    for line, row in enumerate(rows, start=2):
        _required(row, CUSTOMER_REQUIRED, "customers", line)
        ref, email = row["external_customer_ref"], row["email"].casefold()
        if ref in seen_refs:
            raise ImportValidationError(f"customers row {line}: duplicate external_customer_ref {ref}")
        if email in seen_emails:
            raise ImportValidationError(f"customers row {line}: duplicate email {row['email']}")
        seen_refs.add(ref)
        seen_emails.add(email)
        relationship_start = row.get("relationship_start_date") or None
        if relationship_start:
            try:
                date.fromisoformat(relationship_start)
            except ValueError as exc:
                raise ImportValidationError(f"customers row {line}: relationship_start_date must be YYYY-MM-DD") from exc
        output.append({
            "customer_id": stable_id(source_system, "customer", ref),
            "external_customer_ref": ref,
            "full_name": row["full_name"],
            "email": row["email"],
            "account_tier": row.get("account_tier") or "Standard",
            "customer_type": row.get("customer_type") or None,
            "relationship_start_date": relationship_start,
            "branch_code": row.get("branch_code") or None,
            "region_code": row.get("region_code") or None,
            "source_system": source_system,
            "data_origin": "imported",
        })
    return output


def normalize_transaction_rows(
    rows: list[dict[str, str]], source_system: str, customer_ids: dict[str, str], default_currency: str
) -> list[dict[str, Any]]:
    output, seen_refs = [], set()
    for line, row in enumerate(rows, start=2):
        _required(row, TRANSACTION_REQUIRED, "transactions", line)
        ref, customer_ref = row["external_transaction_ref"], row["external_customer_ref"]
        if ref in seen_refs:
            raise ImportValidationError(f"transactions row {line}: duplicate external_transaction_ref {ref}")
        if customer_ref not in customer_ids:
            raise ImportValidationError(f"transactions row {line}: unknown external_customer_ref {customer_ref}")
        seen_refs.add(ref)
        kind = TRANSACTION_TYPES.get(row["transaction_type"].casefold())
        if not kind:
            raise ImportValidationError(f"transactions row {line}: transaction_type must be Debit or Credit")
        status = (row.get("transaction_status") or "posted").casefold()
        if status not in TRANSACTION_STATUSES:
            raise ImportValidationError(f"transactions row {line}: unsupported transaction_status {status}")
        currency = (row.get("currency_code") or default_currency).upper()
        if pycountry.currencies.get(alpha_3=currency) is None:
            raise ImportValidationError(f"transactions row {line}: currency_code must be a recognised ISO 4217 code")
        if currency != default_currency.upper():
            raise ImportValidationError(
                f"transactions row {line}: currency_code {currency} differs from package currency {default_currency.upper()}"
            )
        value_date = row.get("value_date") or None
        if value_date:
            try:
                date.fromisoformat(value_date)
            except ValueError as exc:
                raise ImportValidationError(f"transactions row {line}: value_date must be YYYY-MM-DD") from exc
        output.append({
            "transaction_id": stable_id(source_system, "transaction", ref),
            "customer_id": customer_ids[customer_ref],
            "external_transaction_ref": ref,
            "timestamp": _iso_timestamp(row["timestamp"], "transactions", line),
            "amount": _decimal(row["amount"], "amount", "transactions", line),
            "transaction_type": kind,
            "merchant_category": row["merchant_category"],
            "channel": row["channel"],
            "post_transaction_balance": _decimal(row["post_transaction_balance"], "post_transaction_balance", "transactions", line, allow_negative=True),
            "transaction_status": status,
            "account_ref": row.get("account_ref") or None,
            "currency_code": currency,
            "value_date": value_date,
            "counterparty_category": row.get("counterparty_category") or None,
            "source_system": source_system,
            "data_origin": "imported",
        })
    return output


def file_checksum(paths: list[str | Path]) -> str:
    digest = hashlib.sha256()
    for path in paths:
        digest.update(Path(path).name.encode("utf-8"))
        with open(path, "rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    return digest.hexdigest()


def prepare_import(customers_path: str, transactions_path: str, source_system: str, currency: str):
    if not SOURCE_RE.fullmatch(source_system):
        raise ImportValidationError("source_system must be 2-80 characters: letters, digits, dot, underscore or hyphen")
    currency = currency.upper()
    if pycountry.currencies.get(alpha_3=currency) is None:
        raise ImportValidationError("currency must be a recognised ISO 4217 code")
    customer_rows = _read_csv(customers_path)
    transaction_rows = _read_csv(transactions_path)
    customers = normalize_customer_rows(customer_rows, source_system)
    customer_ids = {row["external_customer_ref"]: row["customer_id"] for row in customers}
    transactions = normalize_transaction_rows(transaction_rows, source_system, customer_ids, currency)
    return customers, transactions, file_checksum([customers_path, transactions_path])


def _chunks(rows: list[dict[str, Any]], size: int = 250):
    for start in range(0, len(rows), size):
        yield rows[start:start + size]


def _canonical(value, field):
    if value is None:
        return None
    if field in {"timestamp"}:
        return _iso_timestamp(str(value), "database", 0)
    if field in {"amount", "post_transaction_balance"}:
        return format(Decimal(str(value)).quantize(Decimal("0.0001")), "f")
    return str(value)


def _existing_records(db, table, id_field, rows):
    existing = {}
    ids = [row[id_field] for row in rows]
    for start in range(0, len(ids), 100):
        result = db.table(table).select("*").in_(id_field, ids[start:start + 100]).execute()
        for row in result.data or []:
            existing[row[id_field]] = row
    return existing


def _separate_new_and_identical(existing, incoming, id_field, fields, table):
    new_rows = []
    for row in incoming:
        current = existing.get(row[id_field])
        if current is None:
            new_rows.append(row)
            continue
        mismatches = [
            field for field in fields
            if _canonical(current.get(field), field) != _canonical(row.get(field), field)
        ]
        if mismatches:
            raise ImportValidationError(
                f"Existing {table} record {row[id_field]} differs from this export "
                f"({', '.join(mismatches)}). No rows have been written; resolve the source correction explicitly."
            )
    return new_rows


def _validate_resume_batch(batch, source_system, currency, checksum, approval_evidence):
    if not batch:
        raise ImportValidationError("resume batch ID was not found")
    if batch.get("status") not in {"validating", "partially_loaded", "failed"}:
        raise ImportValidationError(
            f"batch status {batch.get('status')!r} cannot be resumed; only validating, partially_loaded or failed batches are eligible"
        )
    if batch.get("source_system") != source_system:
        raise ImportValidationError("resume batch source_system does not match this package")
    if str(batch.get("currency_code") or "").strip() != currency:
        raise ImportValidationError("resume batch currency does not match this package")
    if batch.get("checksum_sha256") != checksum:
        raise ImportValidationError("resume batch checksum does not match the exact CSV files")
    metadata = batch.get("metadata") or {}
    previous_approval = metadata.get("approval_evidence") or {}
    if previous_approval.get("approval_reference") != (approval_evidence or {}).get("approval_reference"):
        raise ImportValidationError("resume batch approval reference does not match the validated manifest")
    if previous_approval.get("file_checksum_sha256") != checksum:
        raise ImportValidationError("resume batch does not contain matching approval checksum evidence")
    return metadata


def import_to_supabase(
    customers, transactions, checksum, source_system, currency, file_names,
    approval_evidence=None, resume_batch_id=None,
):
    from supabase import create_client

    url, key = os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise RuntimeError("Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in the local environment")
    db = create_client(url, key)

    # Refuse email collisions rather than mutating or merging unrelated existing records.
    emails = sorted({row["email"] for row in customers})
    for start in range(0, len(emails), 100):
        result = db.table("customers").select("email,customer_id").in_("email", emails[start:start + 100]).execute()
        expected_ids = {row["customer_id"] for row in customers}
        collisions = [row["email"] for row in (result.data or []) if row["customer_id"] not in expected_ids]
        if collisions:
            raise ImportValidationError(
                f"Existing customer email collision(s): {', '.join(collisions[:10])}. "
                "Resolve identity mapping before import; no rows have been written."
            )

    source_customer_count, source_transaction_count = len(customers), len(transactions)
    existing_customers = _existing_records(db, "customers", "customer_id", customers)
    existing_transactions = _existing_records(db, "transactions", "transaction_id", transactions)
    customer_fields = [
        "external_customer_ref", "full_name", "email", "account_tier", "customer_type",
        "relationship_start_date", "branch_code", "region_code", "source_system", "data_origin",
    ]
    transaction_fields = [
        "customer_id", "external_transaction_ref", "timestamp", "amount", "transaction_type",
        "merchant_category", "channel", "post_transaction_balance", "transaction_status",
        "account_ref", "currency_code", "value_date", "counterparty_category", "source_system", "data_origin",
    ]
    new_customers = _separate_new_and_identical(
        existing_customers, customers, "customer_id", customer_fields, "customer"
    )
    new_transactions = _separate_new_and_identical(
        existing_transactions, transactions, "transaction_id", transaction_fields, "transaction"
    )
    if not resume_batch_id and (
        len(new_customers) != source_customer_count
        or len(new_transactions) != source_transaction_count
    ):
        raise ImportValidationError(
            "Some identical source records already exist. Refusing to create a new batch with incomplete lineage; "
            "inspect their import_batch_id values and resume the original eligible batch if this is a recovery."
        )

    if resume_batch_id:
        result = (
            db.table("data_import_batches").select("*")
            .eq("import_batch_id", resume_batch_id).limit(1).execute()
        )
        batch_rows = result.data or []
        batch = batch_rows[0] if batch_rows else None
        _validate_resume_batch(
            batch, source_system, currency, checksum, approval_evidence
        )
        batch_id = batch["import_batch_id"]
        for table_name, existing in (
            ("customers", existing_customers), ("transactions", existing_transactions)
        ):
            wrong_batch = [
                row for row in existing.values()
                if row.get("import_batch_id") != batch_id
            ]
            if wrong_batch:
                raise ImportValidationError(
                    f"Cannot resume: an identical existing {table_name} row is not linked to batch {batch_id}. "
                    "No rows have been written; investigate lineage manually."
                )
        batch_metadata = batch.get("metadata") or {}
        db.table("data_import_batches").update({
            "status": "validating",
            "metadata": {
                **batch_metadata,
                "resume_attempted_at": datetime.now(timezone.utc).isoformat(),
            },
        }).eq("import_batch_id", batch_id).execute()
    else:
        batch = db.table("data_import_batches").insert({
            "source_system": source_system,
            "source_dataset": "BancABC customer and transaction export",
            "source_file_name": ";".join(file_names),
            "data_origin": "imported",
            "status": "validating",
            "currency_code": currency,
            "source_row_count": source_customer_count + source_transaction_count,
            "checksum_sha256": checksum,
            "schema_version": SCHEMA_VERSION,
            "metadata": {
                "source_customer_rows": source_customer_count,
                "source_transaction_rows": source_transaction_count,
                "new_customer_rows": len(new_customers),
                "new_transaction_rows": len(new_transactions),
                "import_method": "bancabc_csv_v1",
                "approval_evidence": approval_evidence or {},
            },
        }).execute().data[0]
        batch_id = batch["import_batch_id"]
        batch_metadata = batch.get("metadata") or {}

    inserted_customers = inserted_transactions = 0
    try:
        for chunk in _chunks(new_customers):
            payload = [{**row, "import_batch_id": batch_id} for row in chunk]
            db.table("customers").insert(payload).execute()
            inserted_customers += len(payload)
        for chunk in _chunks(new_transactions):
            payload = [{**row, "import_batch_id": batch_id} for row in chunk]
            db.table("transactions").insert(payload).execute()
            inserted_transactions += len(payload)

        # Count rows actually carrying this batch's lineage; do not infer from
        # this invocation's counters, which may be zero on a successful resume.
        customer_count = db.table("customers").select("customer_id", count="exact").eq(
            "import_batch_id", batch_id
        ).execute().count or 0
        transaction_count = db.table("transactions").select("transaction_id", count="exact").eq(
            "import_batch_id", batch_id
        ).execute().count or 0
        expected_count = source_customer_count + source_transaction_count
        if customer_count + transaction_count != expected_count:
            raise ImportValidationError(
                f"Batch lineage verification failed: expected {expected_count} rows, "
                f"found {customer_count + transaction_count} linked to batch {batch_id}"
            )
        db.table("data_import_batches").update({
            "status": "loaded",
            "inserted_row_count": customer_count + transaction_count,
            "rejected_row_count": 0,
            "imported_at": batch.get("imported_at") or datetime.now(timezone.utc).isoformat(),
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "metadata": {
                **batch_metadata,
                "verified_customer_rows": customer_count,
                "verified_transaction_rows": transaction_count,
                "last_execution_inserted_customer_rows": inserted_customers,
                "last_execution_inserted_transaction_rows": inserted_transactions,
            },
        }).eq("import_batch_id", batch_id).execute()
    except Exception as exc:
        try:
            actual_customers = db.table("customers").select(
                "customer_id", count="exact"
            ).eq("import_batch_id", batch_id).execute().count or 0
            actual_transactions = db.table("transactions").select(
                "transaction_id", count="exact"
            ).eq("import_batch_id", batch_id).execute().count or 0
            actual_total = actual_customers + actual_transactions
            db.table("data_import_batches").update({
                "status": "partially_loaded" if actual_total else "failed",
                "inserted_row_count": actual_total,
                "rejected_row_count": max(
                    0, source_customer_count + source_transaction_count - actual_total
                ),
                "metadata": {
                    **batch_metadata,
                    "last_failure": str(exc)[:500],
                    "last_failure_at": datetime.now(timezone.utc).isoformat(),
                    "verified_customer_rows": actual_customers,
                    "verified_transaction_rows": actual_transactions,
                    "last_execution_inserted_customer_rows": inserted_customers,
                    "last_execution_inserted_transaction_rows": inserted_transactions,
                },
            }).eq("import_batch_id", batch_id).execute()
        except Exception:
            # Preserve the original write/finalization exception. The batch may
            # remain validating and must be inspected before any retry.
            pass
        raise
    return {
        "status": "loaded",
        "import_batch_id": batch_id,
        "customers_inserted_this_execution": inserted_customers,
        "transactions_inserted_this_execution": inserted_transactions,
        "customers_verified_in_batch": customer_count,
        "transactions_verified_in_batch": transaction_count,
        "resumed_existing_batch": bool(resume_batch_id),
        "checksum_sha256": checksum,
    }



def validate_approval_manifest(
    manifest_path: str,
    customers: list[dict[str, Any]],
    transactions: list[dict[str, Any]],
    source_system: str,
    currency: str,
    checksum: str,
) -> dict[str, Any]:
    """Validate declared source approval and signed control totals before any write.

    This checks package consistency, not the authenticity of the approver. A human
    owner must independently verify the referenced approval evidence.
    """
    try:
        with open(manifest_path, "r", encoding="utf-8") as handle:
            manifest = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise ImportValidationError(f"approval manifest cannot be read: {exc}") from exc
    if not isinstance(manifest, dict):
        raise ImportValidationError("approval manifest root must be a JSON object")
    required = (
        "approval_reference", "approved_by", "approved_at", "source_system",
        "currency_code", "extraction_start", "extraction_end",
        "customer_count", "transaction_count", "debit_total", "credit_total",
        "transaction_amount_total", "file_checksum_sha256",
    )
    missing = [key for key in required if manifest.get(key) in (None, "")]
    if missing:
        raise ImportValidationError(f"approval manifest missing fields: {', '.join(missing)}")
    if manifest["source_system"] != source_system:
        raise ImportValidationError("approval manifest source_system does not match --source-system")
    if str(manifest["currency_code"]).upper() != currency.upper():
        raise ImportValidationError("approval manifest currency_code does not match --currency")
    try:
        approved_at = datetime.fromisoformat(str(manifest["approved_at"]).replace("Z", "+00:00"))
        extraction_start = datetime.fromisoformat(str(manifest["extraction_start"]).replace("Z", "+00:00"))
        extraction_end = datetime.fromisoformat(str(manifest["extraction_end"]).replace("Z", "+00:00"))
    except ValueError as exc:
        raise ImportValidationError("approval and extraction timestamps must be ISO-8601") from exc
    if approved_at.tzinfo is None or extraction_start.tzinfo is None or extraction_end.tzinfo is None:
        raise ImportValidationError("approval and extraction timestamps must include timezone offsets")
    if extraction_start >= extraction_end:
        raise ImportValidationError("extraction_start must be earlier than extraction_end")
    if approved_at > extraction_start:
        raise ImportValidationError("approval timestamp must not be later than extraction_start")
    declared_checksum = manifest["file_checksum_sha256"]
    if not isinstance(declared_checksum, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", declared_checksum):
        raise ImportValidationError("approval manifest file_checksum_sha256 must be a 64-character SHA-256 hex digest")
    if declared_checksum.lower() != checksum.lower():
        raise ImportValidationError("approval manifest file_checksum_sha256 does not match the supplied CSV files")
    expected_counts = {
        "customer_count": len(customers),
        "transaction_count": len(transactions),
    }
    for key, actual in expected_counts.items():
        if isinstance(manifest[key], bool):
            raise ImportValidationError(f"approval manifest {key} must be an integer")
        try:
            declared = int(manifest[key])
        except (TypeError, ValueError) as exc:
            raise ImportValidationError(f"approval manifest {key} must be an integer") from exc
        if declared != actual:
            raise ImportValidationError(f"approval manifest {key} mismatch: declared {declared}, actual {actual}")
    if pycountry.currencies.get(alpha_3=currency.upper()) is None:
        raise ImportValidationError("currency must be a recognised ISO 4217 code")
    totals = {"debit_total": Decimal("0"), "credit_total": Decimal("0")}
    for row in transactions:
        if row["currency_code"].upper() != currency.upper():
            raise ImportValidationError("transaction currency differs from approved package currency")
        transaction_time = datetime.fromisoformat(row["timestamp"].replace("Z", "+00:00"))
        if not (extraction_start.astimezone(timezone.utc) <= transaction_time < extraction_end.astimezone(timezone.utc)):
            raise ImportValidationError("transaction timestamp falls outside the approved extraction window")
        totals["debit_total" if row["transaction_type"] == "Debit" else "credit_total"] += Decimal(row["amount"])
    totals["transaction_amount_total"] = totals["debit_total"] + totals["credit_total"]
    for key, actual in totals.items():
        try:
            declared = Decimal(str(manifest[key])).quantize(Decimal("0.0001"))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise ImportValidationError(f"approval manifest {key} must be a decimal amount") from exc
        if not declared.is_finite() or declared != actual.quantize(Decimal("0.0001")):
            raise ImportValidationError(f"approval manifest {key} mismatch: declared {declared}, actual {actual}")
    return {
        "approval_reference": str(manifest["approval_reference"]),
        "approved_by": str(manifest["approved_by"]),
        "approved_at": approved_at.astimezone(timezone.utc).isoformat(),
        "extraction_start": extraction_start.astimezone(timezone.utc).isoformat(),
        "extraction_end": extraction_end.astimezone(timezone.utc).isoformat(),
        "customer_count": len(customers),
        "transaction_count": len(transactions),
        **{key: str(value.quantize(Decimal("0.0001"))) for key, value in totals.items()},
        "currency_code": currency.upper(),
        "file_checksum_sha256": checksum,
    }



def build_import_readiness_report(
    customers: list[dict[str, Any]],
    transactions: list[dict[str, Any]],
    checksum: str,
    source_system: str,
    currency: str,
    approval: dict[str, Any] | None,
) -> dict[str, Any]:
    """Produce aggregate-only dry-run evidence for source-owner reconciliation."""
    debit = sum(
        (Decimal(row["amount"]) for row in transactions if row["transaction_type"] == "Debit"),
        Decimal("0"),
    )
    credit = sum(
        (Decimal(row["amount"]) for row in transactions if row["transaction_type"] == "Credit"),
        Decimal("0"),
    )
    timestamps = [datetime.fromisoformat(row["timestamp"].replace("Z", "+00:00")) for row in transactions]
    branch_by_customer = {
        row["customer_id"]: str(row.get("branch_code") or "UNSPECIFIED")
        for row in customers
    }
    branch_totals: dict[str, dict[str, Decimal | int]] = {}
    status_counts = Counter()
    for row in transactions:
        branch = branch_by_customer.get(row["customer_id"], "UNMAPPED")
        bucket = branch_totals.setdefault(
            branch, {"transaction_count": 0, "debit_total": Decimal("0"), "credit_total": Decimal("0")}
        )
        bucket["transaction_count"] += 1
        bucket["debit_total" if row["transaction_type"] == "Debit" else "credit_total"] += Decimal(row["amount"])
        status_counts[row["transaction_status"]] += 1
    return {
        "mode": "dry_run",
        "readiness": "approval_manifest_validated" if approval else "awaiting_approval_manifest",
        "source_system": source_system,
        "currency_code": currency.upper(),
        "data_origin": "imported",
        "customers_validated": len(customers),
        "transactions_validated": len(transactions),
        "checksum_sha256": checksum,
        "transaction_time_range_utc": {
            "start": min(timestamps).isoformat() if timestamps else None,
            "end": max(timestamps).isoformat() if timestamps else None,
        },
        "transaction_status_counts": dict(sorted(status_counts.items())),
        "source_reconciliation": {
            "debit_total": str(debit.quantize(Decimal("0.0001"))),
            "credit_total": str(credit.quantize(Decimal("0.0001"))),
            "transaction_amount_total": str((debit + credit).quantize(Decimal("0.0001"))),
            "branch_totals": {
                branch: {
                    "transaction_count": int(values["transaction_count"]),
                    "debit_total": str(values["debit_total"].quantize(Decimal("0.0001"))),
                    "credit_total": str(values["credit_total"].quantize(Decimal("0.0001"))),
                }
                for branch, values in sorted(branch_totals.items())
            },
        },
        "approval_manifest_validated": approval is not None,
        "approval_reference": approval.get("approval_reference") if approval else None,
    }




def build_batch_verification_report(
    batch: dict[str, Any] | None,
    batch_customers: list[dict[str, Any]],
    batch_transactions: list[dict[str, Any]],
    customers: list[dict[str, Any]],
    transactions: list[dict[str, Any]],
    checksum: str,
    source_system: str,
    currency: str,
    approval: dict[str, Any],
) -> dict[str, Any]:
    """Compare one batch against the exact approved package without writing data."""
    errors: list[str] = []
    if not batch:
        return {"verification_status": "not_found", "verified": False, "errors": ["import batch was not found"]}
    if batch.get("source_system") != source_system:
        errors.append("source_system_mismatch")
    if str(batch.get("currency_code") or "").strip() != currency.upper():
        errors.append("currency_mismatch")
    if batch.get("checksum_sha256") != checksum:
        errors.append("checksum_mismatch")
    metadata = batch.get("metadata") or {}
    evidence = metadata.get("approval_evidence") or {}
    if evidence.get("approval_reference") != approval.get("approval_reference"):
        errors.append("approval_reference_mismatch")
    if evidence.get("file_checksum_sha256") != checksum:
        errors.append("approval_checksum_mismatch")

    customer_fields = [
        "external_customer_ref", "full_name", "email", "account_tier", "customer_type",
        "relationship_start_date", "branch_code", "region_code", "source_system", "data_origin",
    ]
    transaction_fields = [
        "customer_id", "external_transaction_ref", "timestamp", "amount", "transaction_type",
        "merchant_category", "channel", "post_transaction_balance", "transaction_status",
        "account_ref", "currency_code", "value_date", "counterparty_category", "source_system", "data_origin",
    ]

    def compare_rows(expected_rows, actual_rows, id_field, fields, label):
        expected = {row[id_field]: row for row in expected_rows}
        actual = {row[id_field]: row for row in actual_rows}
        missing = set(expected) - set(actual)
        unexpected = set(actual) - set(expected)
        mismatched = 0
        wrong_lineage = 0
        for record_id in set(expected) & set(actual):
            current = actual[record_id]
            if current.get("import_batch_id") != batch.get("import_batch_id"):
                wrong_lineage += 1
            if any(
                _canonical(current.get(field), field) != _canonical(expected[record_id].get(field), field)
                for field in fields
            ):
                mismatched += 1
        if missing:
            errors.append(f"{label}_missing_rows")
        if unexpected:
            errors.append(f"{label}_unexpected_rows")
        if mismatched:
            errors.append(f"{label}_source_value_mismatches")
        if wrong_lineage:
            errors.append(f"{label}_lineage_mismatches")
        return {
            "expected": len(expected), "found": len(actual), "missing": len(missing),
            "unexpected": len(unexpected), "source_value_mismatches": mismatched,
            "lineage_mismatches": wrong_lineage,
        }

    customer_result = compare_rows(customers, batch_customers, "customer_id", customer_fields, "customer")
    transaction_result = compare_rows(transactions, batch_transactions, "transaction_id", transaction_fields, "transaction")
    expected_total = len(customers) + len(transactions)
    if batch.get("source_row_count") != expected_total:
        errors.append("batch_source_row_count_mismatch")
    if metadata.get("source_customer_rows") != len(customers):
        errors.append("batch_customer_manifest_count_mismatch")
    if metadata.get("source_transaction_rows") != len(transactions):
        errors.append("batch_transaction_manifest_count_mismatch")
    batch_status = batch.get("status")
    if batch_status != "loaded":
        errors.append("batch_not_marked_loaded")
    verified = not errors
    return {
        "verification_status": "verified" if verified else "mismatch",
        "verified": verified,
        "import_batch_id": batch.get("import_batch_id"),
        "batch_status": batch_status,
        "source_system": source_system,
        "currency_code": currency.upper(),
        "checksum_sha256": checksum,
        "approval_reference": approval.get("approval_reference"),
        "customers": customer_result,
        "transactions": transaction_result,
        "expected_total_rows": expected_total,
        "found_total_rows": len(batch_customers) + len(batch_transactions),
        "errors": errors,
        "read_only": True,
    }


def verify_import_batch(db, batch_id, customers, transactions, checksum, source_system, currency, approval):
    batch_result = db.table("data_import_batches").select("*").eq("import_batch_id", batch_id).limit(1).execute()
    batch_rows = batch_result.data or []
    batch = batch_rows[0] if batch_rows else None
    if not batch:
        return build_batch_verification_report(None, [], [], customers, transactions, checksum, source_system, currency, approval)
    customer_result = db.table("customers").select("*").eq("import_batch_id", batch_id).execute()
    transaction_result = db.table("transactions").select("*").eq("import_batch_id", batch_id).execute()
    return build_batch_verification_report(
        batch, customer_result.data or [], transaction_result.data or [],
        customers, transactions, checksum, source_system, currency, approval,
    )


def main():
    parser = argparse.ArgumentParser(description="Validate or import an approved BancABC CSV export.")
    parser.add_argument("--customers", required=True, help="Customer CSV file")
    parser.add_argument("--transactions", required=True, help="Transaction CSV file")
    parser.add_argument("--source-system", required=True, help="Stable source identifier, e.g. bancabc_core_banking")
    parser.add_argument("--currency", required=True, help="Default ISO 4217 currency code for transaction rows")
    parser.add_argument("--approval-manifest", help="JSON manifest containing owner approval reference and source control totals")
    parser.add_argument("--resume-batch-id", help="Resume an existing failed/partial batch only when its checksum and approval evidence match")
    parser.add_argument("--verify-batch-id", help="Read-only verification of a batch against the exact approved CSV package")
    parser.add_argument("--apply", action="store_true", help="Write to Supabase; requires a validated --approval-manifest")
    args = parser.parse_args()
    try:
        customers, transactions, checksum = prepare_import(
            args.customers, args.transactions, args.source_system, args.currency
        )
        approval = None
        if args.approval_manifest:
            approval = validate_approval_manifest(
                args.approval_manifest, customers, transactions, args.source_system,
                args.currency.upper(), checksum
            )
        if args.apply and approval is None:
            raise ImportValidationError("--apply requires --approval-manifest with matching approval and control totals")
        if args.resume_batch_id and not args.apply:
            raise ImportValidationError("--resume-batch-id requires --apply")
        if args.verify_batch_id and args.apply:
            raise ImportValidationError("--verify-batch-id is read-only and cannot be combined with --apply")
        if args.verify_batch_id and approval is None:
            raise ImportValidationError("--verify-batch-id requires --approval-manifest")
        if args.verify_batch_id and args.resume_batch_id:
            raise ImportValidationError("--verify-batch-id cannot be combined with --resume-batch-id")
        summary = build_import_readiness_report(
            customers, transactions, checksum, args.source_system,
            args.currency.upper(), approval
        )
        if args.verify_batch_id:
            from supabase import create_client
            url, key = os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_ROLE_KEY")
            if not url or not key:
                raise RuntimeError("Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in the local environment")
            db = create_client(url, key)
            verification = verify_import_batch(
                db, args.verify_batch_id, customers, transactions, checksum,
                args.source_system, args.currency.upper(), approval
            )
            print(json.dumps(verification, indent=2))
            if not verification["verified"]:
                raise SystemExit(3)
            return
        if args.apply:
            summary["mode"] = "apply"
        if args.apply:
            summary.update(import_to_supabase(
                customers, transactions, checksum, args.source_system,
                args.currency.upper(), [Path(args.customers).name, Path(args.transactions).name],
                approval, args.resume_batch_id
            ))
        print(json.dumps(summary, indent=2))
    except (ImportValidationError, RuntimeError) as exc:
        print(json.dumps({"status": "rejected", "error": str(exc)}, indent=2), file=sys.stderr)
        raise SystemExit(2)


if __name__ == "__main__":
    main()
