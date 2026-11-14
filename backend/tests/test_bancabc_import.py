import json
from decimal import Decimal

import pytest

from bancabc_import import (
    ImportValidationError,
    normalize_customer_rows,
    normalize_transaction_rows,
    stable_id,
    validate_approval_manifest,
    build_import_readiness_report,
)


def customer(ref="C-001", email="one@example.com"):
    return {"external_customer_ref": ref, "full_name": "Test Customer", "email": email}


def transaction(ref="T-001", customer_ref="C-001"):
    return {
        "external_transaction_ref": ref,
        "external_customer_ref": customer_ref,
        "timestamp": "2026-10-01T10:30:00+02:00",
        "amount": "125.50",
        "transaction_type": "debit",
        "merchant_category": "Groceries",
        "channel": "Mobile",
        "post_transaction_balance": "874.50",
    }


def test_customer_ids_are_stable_and_provenance_is_explicit():
    first = normalize_customer_rows([customer()], "bancabc_core")
    second = normalize_customer_rows([customer()], "bancabc_core")
    assert first == second
    assert first[0]["customer_id"] == stable_id("bancabc_core", "customer", "C-001")
    assert first[0]["data_origin"] == "imported"


def test_duplicate_customer_reference_is_rejected():
    with pytest.raises(ImportValidationError, match="duplicate external_customer_ref"):
        normalize_customer_rows([customer(), customer(email="two@example.com")], "bancabc_core")


def test_duplicate_customer_email_is_rejected_case_insensitively():
    with pytest.raises(ImportValidationError, match="duplicate email"):
        normalize_customer_rows([customer(), customer("C-002", "ONE@example.com")], "bancabc_core")


def test_transaction_is_normalized_with_stable_customer_link_and_utc_time():
    customers = normalize_customer_rows([customer()], "bancabc_core")
    mapping = {customers[0]["external_customer_ref"]: customers[0]["customer_id"]}
    rows = normalize_transaction_rows([transaction()], "bancabc_core", mapping, "USD")
    assert rows[0]["customer_id"] == customers[0]["customer_id"]
    assert rows[0]["timestamp"] == "2026-10-01T08:30:00+00:00"
    assert rows[0]["transaction_type"] == "Debit"
    assert rows[0]["data_origin"] == "imported"


def test_unknown_customer_reference_is_rejected():
    with pytest.raises(ImportValidationError, match="unknown external_customer_ref"):
        normalize_transaction_rows([transaction(customer_ref="MISSING")], "bancabc_core", {}, "USD")


def test_naive_transaction_timestamp_is_rejected():
    row = transaction()
    row["timestamp"] = "2026-10-01 10:30:00"
    customers = normalize_customer_rows([customer()], "bancabc_core")
    mapping = {customers[0]["external_customer_ref"]: customers[0]["customer_id"]}
    with pytest.raises(ImportValidationError, match="must include a timezone"):
        normalize_transaction_rows([row], "bancabc_core", mapping, "USD")


def test_negative_transaction_amount_is_rejected():
    row = transaction()
    row["amount"] = "-10"
    customers = normalize_customer_rows([customer()], "bancabc_core")
    mapping = {customers[0]["external_customer_ref"]: customers[0]["customer_id"]}
    with pytest.raises(ImportValidationError, match="cannot be negative"):
        normalize_transaction_rows([row], "bancabc_core", mapping, "USD")



def test_approval_manifest_must_match_counts_totals_currency_and_checksum(tmp_path):
    customers = normalize_customer_rows([customer()], "bancabc_core")
    mapping = {customers[0]["external_customer_ref"]: customers[0]["customer_id"]}
    transactions = normalize_transaction_rows(
        [transaction()], "bancabc_core", mapping, "USD"
    )
    manifest = {
        "approval_reference": "DATA-APPROVAL-2026-001",
        "approved_by": "BancABC Data Owner",
        "approved_at": "2026-09-30T09:00:00+02:00",
        "source_system": "bancabc_core",
        "currency_code": "USD",
        "extraction_start": "2026-10-01T00:00:00+02:00",
        "extraction_end": "2026-11-01T00:00:00+02:00",
        "customer_count": 1,
        "transaction_count": 1,
        "debit_total": "125.5000",
        "credit_total": "0.0000",
        "transaction_amount_total": "125.5000",
        "file_checksum_sha256": "a" * 64,
    }
    path = tmp_path / "approval.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    result = validate_approval_manifest(
        str(path), customers, transactions, "bancabc_core", "USD", "a" * 64
    )
    assert result["approval_reference"] == "DATA-APPROVAL-2026-001"
    assert result["debit_total"] == "125.5000"
    assert result["transaction_amount_total"] == "125.5000"


def test_approval_manifest_rejects_mismatched_source_control_total(tmp_path):
    customers = normalize_customer_rows([customer()], "bancabc_core")
    mapping = {customers[0]["external_customer_ref"]: customers[0]["customer_id"]}
    transactions = normalize_transaction_rows(
        [transaction()], "bancabc_core", mapping, "USD"
    )
    manifest = {
        "approval_reference": "DATA-APPROVAL-2026-001",
        "approved_by": "BancABC Data Owner",
        "approved_at": "2026-11-14T09:00:00+02:00",
        "source_system": "bancabc_core",
        "currency_code": "USD",
        "extraction_start": "2026-10-01T00:00:00+02:00",
        "extraction_end": "2026-11-01T00:00:00+02:00",
        "customer_count": 1,
        "transaction_count": 1,
        "debit_total": "125.4900",
        "credit_total": "0.0000",
        "transaction_amount_total": "125.4900",
        "file_checksum_sha256": "b" * 64,
    }
    path = tmp_path / "approval.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ImportValidationError, match="file_checksum_sha256"):
        validate_approval_manifest(
            str(path), customers, transactions, "bancabc_core", "USD", "a" * 64
        )



def test_non_iso_currency_code_is_rejected():
    customers = normalize_customer_rows([customer()], "bancabc_core")
    mapping = {customers[0]["external_customer_ref"]: customers[0]["customer_id"]}
    with pytest.raises(ImportValidationError, match="recognised ISO 4217"):
        normalize_transaction_rows([transaction()], "bancabc_core", mapping, "ZZZ")


def test_transaction_currency_must_match_approved_package_currency():
    row = transaction()
    row["currency_code"] = "ZAR"
    customers = normalize_customer_rows([customer()], "bancabc_core")
    mapping = {customers[0]["external_customer_ref"]: customers[0]["customer_id"]}
    with pytest.raises(ImportValidationError, match="differs from package currency"):
        normalize_transaction_rows([row], "bancabc_core", mapping, "USD")


def test_manifest_rejects_transaction_outside_extraction_window(tmp_path):
    customers = normalize_customer_rows([customer()], "bancabc_core")
    mapping = {customers[0]["external_customer_ref"]: customers[0]["customer_id"]}
    row = transaction()
    row["timestamp"] = "2026-12-01T10:30:00+02:00"
    transactions = normalize_transaction_rows([row], "bancabc_core", mapping, "USD")
    manifest = {
        "approval_reference": "DATA-APPROVAL-2026-001",
        "approved_by": "BancABC Data Owner",
        "approved_at": "2026-09-30T09:00:00+02:00",
        "source_system": "bancabc_core",
        "currency_code": "USD",
        "extraction_start": "2026-10-01T00:00:00+02:00",
        "extraction_end": "2026-11-01T00:00:00+02:00",
        "customer_count": 1,
        "transaction_count": 1,
        "debit_total": "125.5000",
        "credit_total": "0.0000",
        "transaction_amount_total": "125.5000",
        "file_checksum_sha256": "c" * 64,
    }
    path = tmp_path / "approval.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ImportValidationError, match="outside the approved extraction window"):
        validate_approval_manifest(
            str(path), customers, transactions, "bancabc_core", "USD", "c" * 64
        )


def test_manifest_requires_approval_before_extraction_start(tmp_path):
    customers = normalize_customer_rows([customer()], "bancabc_core")
    mapping = {customers[0]["external_customer_ref"]: customers[0]["customer_id"]}
    transactions = normalize_transaction_rows(
        [transaction()], "bancabc_core", mapping, "USD"
    )
    manifest = {
        "approval_reference": "DATA-APPROVAL-2026-001",
        "approved_by": "BancABC Data Owner",
        "approved_at": "2026-10-02T09:00:00+02:00",
        "source_system": "bancabc_core",
        "currency_code": "USD",
        "extraction_start": "2026-10-01T00:00:00+02:00",
        "extraction_end": "2026-11-01T00:00:00+02:00",
        "customer_count": 1,
        "transaction_count": 1,
        "debit_total": "125.5000",
        "credit_total": "0.0000",
        "transaction_amount_total": "125.5000",
        "file_checksum_sha256": "d" * 64,
    }
    path = tmp_path / "approval.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ImportValidationError, match="approval timestamp must not be later"):
        validate_approval_manifest(
            str(path), customers, transactions, "bancabc_core", "USD", "d" * 64
        )



def test_readiness_report_contains_aggregate_reconciliation_and_branch_totals():
    customer_row = customer()
    customer_row["branch_code"] = "HARARE-01"
    customers = normalize_customer_rows([customer_row], "bancabc_core")
    mapping = {customers[0]["external_customer_ref"]: customers[0]["customer_id"]}
    debit = transaction()
    credit = transaction(ref="T-002")
    credit["transaction_type"] = "credit"
    credit["amount"] = "50.25"
    transactions = normalize_transaction_rows(
        [debit, credit], "bancabc_core", mapping, "USD"
    )
    report = build_import_readiness_report(
        customers, transactions, "e" * 64, "bancabc_core", "USD", None
    )
    assert report["readiness"] == "awaiting_approval_manifest"
    assert report["source_reconciliation"]["debit_total"] == "125.5000"
    assert report["source_reconciliation"]["credit_total"] == "50.2500"
    assert report["source_reconciliation"]["transaction_amount_total"] == "175.7500"
    assert report["source_reconciliation"]["branch_totals"]["HARARE-01"]["transaction_count"] == 2
    assert report["transaction_status_counts"] == {"posted": 2}
