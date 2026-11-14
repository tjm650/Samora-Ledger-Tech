import pytest

from bancabc_import import (
    ImportValidationError,
    normalize_customer_rows,
    normalize_transaction_rows,
    stable_id,
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
