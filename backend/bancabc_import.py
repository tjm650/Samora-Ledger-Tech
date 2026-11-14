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
            "approval_manifest_validated": approval is not None,
            "approval_evidence": approval,
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
        if not re.fullmatch(r"[A-Z]{3}", currency):
            raise ImportValidationError(f"transactions row {line}: currency_code must be a 3-letter ISO code")
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
    if not re.fullmatch(r"[A-Z]{3}", currency):
        raise ImportValidationError("currency must be a 3-letter ISO code")
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


def import_to_supabase(customers, transactions, checksum, source_system, currency, file_names):
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
    customers = _separate_new_and_identical(
        existing_customers, customers, "customer_id", customer_fields, "customer"
    )
    transactions = _separate_new_and_identical(
        existing_transactions, transactions, "transaction_id", transaction_fields, "transaction"
    )

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
        "metadata": {"source_customer_rows": source_customer_count, "source_transaction_rows": source_transaction_count, "new_customer_rows": len(customers), "new_transaction_rows": len(transactions), "import_method": "bancabc_csv_v1"},
    }).execute().data[0]
    batch_id = batch["import_batch_id"]
    inserted_customers = inserted_transactions = 0
    try:
        for chunk in _chunks(customers):
            payload = [{**row, "import_batch_id": batch_id} for row in chunk]
            db.table("customers").insert(payload).execute()
            inserted_customers += len(payload)
        for chunk in _chunks(transactions):
            payload = [{**row, "import_batch_id": batch_id} for row in chunk]
            db.table("transactions").insert(payload).execute()
            inserted_transactions += len(payload)
        db.table("data_import_batches").update({
            "status": "loaded",
            "inserted_row_count": inserted_customers + inserted_transactions,
            "rejected_row_count": 0,
            "imported_at": datetime.now(timezone.utc).isoformat(),
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }).eq("import_batch_id", batch_id).execute()
    except Exception as exc:
        db.table("data_import_batches").update({
            "status": "partially_loaded" if inserted_customers or inserted_transactions else "failed",
            "inserted_row_count": inserted_customers + inserted_transactions,
            "rejected_row_count": len(customers) + len(transactions) - inserted_customers - inserted_transactions,
            "metadata": {**batch.get("metadata", {}), "failure": str(exc)[:500]},
        }).eq("import_batch_id", batch_id).execute()
        raise
    return {
        "status": "loaded", "import_batch_id": batch_id,
        "customers_inserted_or_updated": inserted_customers,
        "transactions_inserted_or_updated": inserted_transactions,
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
    if manifest["file_checksum_sha256"].lower() != checksum.lower():
        raise ImportValidationError("approval manifest file_checksum_sha256 does not match the supplied CSV files")
    expected_counts = {
        "customer_count": len(customers),
        "transaction_count": len(transactions),
    }
    for key, actual in expected_counts.items():
        try:
            declared = int(manifest[key])
        except (TypeError, ValueError) as exc:
            raise ImportValidationError(f"approval manifest {key} must be an integer") from exc
        if declared != actual:
            raise ImportValidationError(f"approval manifest {key} mismatch: declared {declared}, actual {actual}")
    totals = {"debit_total": Decimal("0"), "credit_total": Decimal("0")}
    for row in transactions:
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


def main():
    parser = argparse.ArgumentParser(description="Validate or import an approved BancABC CSV export.")
    parser.add_argument("--customers", required=True, help="Customer CSV file")
    parser.add_argument("--transactions", required=True, help="Transaction CSV file")
    parser.add_argument("--source-system", required=True, help="Stable source identifier, e.g. bancabc_core_banking")
    parser.add_argument("--currency", required=True, help="Default ISO 4217 currency code for transaction rows")
    parser.add_argument("--approval-manifest", help="JSON manifest containing owner approval reference and signed source control totals")
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
        summary = {
            "mode": "apply" if args.apply else "dry_run",
            "customers_validated": len(customers),
            "transactions_validated": len(transactions),
            "checksum_sha256": checksum,
            "source_system": args.source_system,
            "data_origin": "imported",
        }
        if args.apply:
            summary.update(import_to_supabase(
                customers, transactions, checksum, args.source_system,
                args.currency.upper(), [Path(args.customers).name, Path(args.transactions).name]
            ))
        print(json.dumps(summary, indent=2))
    except (ImportValidationError, RuntimeError) as exc:
        print(json.dumps({"status": "rejected", "error": str(exc)}, indent=2), file=sys.stderr)
        raise SystemExit(2)


if __name__ == "__main__":
    main()
