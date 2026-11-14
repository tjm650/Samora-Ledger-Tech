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
    _validate_resume_batch,
    build_batch_verification_report,
    import_to_supabase,
    _select_all,
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



def approval_evidence(checksum, reference="BANK-APPROVAL-TEST"):
    return {
        "approval_reference": reference,
        "approved_by": "Approved Data Owner",
        "approved_at": "2026-09-30T07:00:00+00:00",
        "extraction_start": "2026-09-30T22:00:00+00:00",
        "extraction_end": "2026-10-31T22:00:00+00:00",
        "customer_count": 1,
        "transaction_count": 1,
        "debit_total": "125.5000",
        "credit_total": "0.0000",
        "transaction_amount_total": "125.5000",
        "currency_code": "USD",
        "file_checksum_sha256": checksum,
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


def test_approval_manifest_rejects_mismatched_file_checksum(tmp_path):
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



def test_approval_manifest_rejects_mismatched_source_control_total(tmp_path):
    customers = normalize_customer_rows([customer()], "bancabc_core")
    mapping = {customers[0]["external_customer_ref"]: customers[0]["customer_id"]}
    transactions = normalize_transaction_rows(
        [transaction()], "bancabc_core", mapping, "USD"
    )
    manifest = {
        "approval_reference": "DATA-APPROVAL-2026-002",
        "approved_by": "BancABC Data Owner",
        "approved_at": "2026-09-30T09:00:00+02:00",
        "source_system": "bancabc_core",
        "currency_code": "USD",
        "extraction_start": "2026-10-01T00:00:00+02:00",
        "extraction_end": "2026-11-01T00:00:00+02:00",
        "customer_count": 1,
        "transaction_count": 1,
        "debit_total": "125.4900",
        "credit_total": "0.0000",
        "transaction_amount_total": "125.4900",
        "file_checksum_sha256": "f" * 64,
    }
    path = tmp_path / "approval.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ImportValidationError, match="debit_total mismatch"):
        validate_approval_manifest(
            str(path), customers, transactions, "bancabc_core", "USD", "f" * 64
        )



def test_resume_batch_requires_matching_source_currency_checksum_and_approval():
    approval = {"approval_reference": "BANK-APPROVAL-17", "file_checksum_sha256": "a" * 64}
    batch = {
        "import_batch_id": "batch-1",
        "status": "partially_loaded",
        "source_system": "bancabc_core",
        "currency_code": "USD",
        "checksum_sha256": "a" * 64,
        "metadata": {"approval_evidence": approval},
    }
    assert _validate_resume_batch(
        batch, "bancabc_core", "USD", "a" * 64, approval
    )["approval_evidence"] == approval


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"status": "loaded"}, "cannot be resumed"),
        ({"source_system": "other_core"}, "source_system"),
        ({"currency_code": "ZAR"}, "currency"),
        ({"checksum_sha256": "b" * 64}, "checksum"),
        ({"metadata": {"approval_evidence": {"approval_reference": "OTHER", "file_checksum_sha256": "a" * 64}}}, "approval evidence"),
        ({"metadata": {"approval_evidence": {"approval_reference": "BANK-APPROVAL-17", "approved_by": "Different Owner", "file_checksum_sha256": "a" * 64}}}, "approval evidence"),
    ],
)
def test_resume_batch_rejects_incompatible_batch(change, message):
    approval = {"approval_reference": "BANK-APPROVAL-17", "file_checksum_sha256": "a" * 64}
    batch = {
        "import_batch_id": "batch-1",
        "status": "partially_loaded",
        "source_system": "bancabc_core",
        "currency_code": "USD",
        "checksum_sha256": "a" * 64,
        "metadata": {"approval_evidence": approval},
    }
    batch.update(change)
    with pytest.raises(ImportValidationError, match=message):
        _validate_resume_batch(batch, "bancabc_core", "USD", "a" * 64, approval)



def test_batch_verification_requires_exact_rows_values_lineage_and_loaded_status():
    customers = normalize_customer_rows([customer()], "bancabc_core")
    customer_ids = {customers[0]["external_customer_ref"]: customers[0]["customer_id"]}
    transactions = normalize_transaction_rows(
        [transaction()], "bancabc_core", customer_ids, "USD"
    )
    batch_id = "batch-verified"
    batch_customers = [{**customers[0], "import_batch_id": batch_id}]
    batch_transactions = [{**transactions[0], "import_batch_id": batch_id}]
    checksum = "a" * 64
    approval = approval_evidence(checksum, "BANK-APPROVAL-17")
    batch = {
        "import_batch_id": batch_id,
        "status": "loaded",
        "source_system": "bancabc_core",
        "currency_code": "USD",
        "checksum_sha256": checksum,
        "source_row_count": 2,
        "metadata": {
            "source_customer_rows": 1,
            "source_transaction_rows": 1,
            "approval_evidence": approval,
        },
    }
    report = build_batch_verification_report(
        batch, batch_customers, batch_transactions, customers, transactions,
        checksum, "bancabc_core", "USD", approval,
    )
    assert report["verified"] is True
    assert report["verification_status"] == "verified"
    assert report["customers"]["found"] == 1
    assert report["transactions"]["found"] == 1
    assert report["control_totals"]["database_debit"] == "125.5000"
    assert report["control_totals"]["database_credit"] == "0.0000"
    assert report["transaction_status_counts"] == {"posted": 1}
    assert report["read_only"] is True


def test_batch_verification_detects_missing_extra_modified_and_wrong_lineage_rows():
    customers = normalize_customer_rows([customer()], "bancabc_core")
    customer_ids = {customers[0]["external_customer_ref"]: customers[0]["customer_id"]}
    transactions = normalize_transaction_rows(
        [transaction()], "bancabc_core", customer_ids, "USD"
    )
    checksum = "b" * 64
    approval = approval_evidence(checksum, "BANK-APPROVAL-18")
    batch_id = "batch-incomplete"
    altered_customer = {**customers[0], "full_name": "Altered Name", "import_batch_id": "other-batch"}
    extra_customer = {**customers[0], "customer_id": "unexpected-id", "import_batch_id": batch_id}
    batch = {
        "import_batch_id": batch_id,
        "status": "partially_loaded",
        "source_system": "bancabc_core",
        "currency_code": "USD",
        "checksum_sha256": checksum,
        "source_row_count": 2,
        "metadata": {
            "source_customer_rows": 1,
            "source_transaction_rows": 1,
            "approval_evidence": approval,
        },
    }
    report = build_batch_verification_report(
        batch, [altered_customer, extra_customer], [], customers, transactions,
        checksum, "bancabc_core", "USD", approval,
    )
    assert report["verified"] is False
    assert "customer_unexpected_rows" in report["errors"]
    assert "customer_source_value_mismatches" in report["errors"]
    assert "customer_lineage_mismatches" in report["errors"]
    assert "transaction_missing_rows" in report["errors"]
    assert "batch_not_marked_loaded" in report["errors"]


def test_batch_verification_reports_missing_batch_without_database_writes():
    customers = normalize_customer_rows([customer()], "bancabc_core")
    checksum = "c" * 64
    approval = approval_evidence(checksum, "BANK-APPROVAL-19")
    report = build_batch_verification_report(
        None, [], [], customers, [], checksum, "bancabc_core", "USD", approval
    )
    assert report["verification_status"] == "not_found"
    assert report["verified"] is False



@pytest.mark.parametrize(
    ("failure_table", "commit_before_failure"),
    [("customers", True), ("transactions", False)],
)
def test_partial_import_failure_is_lineaged_and_safely_resumable(
    monkeypatch, failure_table, commit_before_failure
):
    import sys
    from types import SimpleNamespace

    customer_rows = normalize_customer_rows([customer()], "bancabc_core")
    customer_ids = {customer_rows[0]["external_customer_ref"]: customer_rows[0]["customer_id"]}
    transaction_rows = normalize_transaction_rows(
        [transaction()], "bancabc_core", customer_ids, "USD"
    )
    checksum = "d" * 64
    approval = {
        "approval_reference": "BANK-APPROVAL-RECOVERY",
        "approved_by": "Approved Data Owner",
        "approved_at": "2026-09-30T07:00:00+00:00",
        "extraction_start": "2026-09-30T22:00:00+00:00",
        "extraction_end": "2026-10-31T22:00:00+00:00",
        "customer_count": 1,
        "transaction_count": 1,
        "debit_total": "125.5000",
        "credit_total": "0.0000",
        "transaction_amount_total": "125.5000",
        "currency_code": "USD",
        "file_checksum_sha256": checksum,
    }

    class FakeQuery:
        def __init__(self, db, table):
            self.db, self.table_name = db, table
            self.operation, self.payload = "select", None
            self.filters, self.in_filters, self.want_count = {}, {}, False
            self.page_range = None

        def select(self, *_args, **kwargs):
            self.operation = "select"
            self.want_count = kwargs.get("count") == "exact"
            return self

        def in_(self, field, values):
            self.in_filters[field] = set(values)
            return self

        def eq(self, field, value):
            self.filters[field] = value
            return self

        def limit(self, _value):
            return self

        def range(self, start, end):
            self.page_range = (start, end)
            return self

        def insert(self, payload):
            self.operation, self.payload = "insert", payload
            return self

        def update(self, payload):
            self.operation, self.payload = "update", payload
            return self

        def execute(self):
            rows = self.db.tables.setdefault(self.table_name, [])
            if self.operation == "select":
                selected = [
                    row for row in rows
                    if all(row.get(k) == v for k, v in self.filters.items())
                    and all(row.get(k) in values for k, values in self.in_filters.items())
                ]
                if self.page_range:
                    start, end = self.page_range
                    selected = selected[start:end + 1]
                return SimpleNamespace(data=selected, count=len(selected) if self.want_count else None)
            if self.operation == "insert":
                payload = self.payload if isinstance(self.payload, list) else [self.payload]
                if self.table_name == "data_import_batches":
                    for row in payload:
                        row.setdefault("import_batch_id", "batch-recovery-test")
                should_fail = self.db.failure and self.db.failure[0] == self.table_name and not self.db.failed
                if should_fail and commit_before_failure:
                    rows.extend(payload)
                if should_fail:
                    self.db.failed = True
                    raise RuntimeError(f"injected {self.table_name} insert failure")
                rows.extend(payload)
                return SimpleNamespace(data=payload, count=None)
            if self.operation == "update":
                updated = []
                for row in rows:
                    if all(row.get(k) == v for k, v in self.filters.items()):
                        row.update(self.payload)
                        updated.append(row)
                return SimpleNamespace(data=updated, count=None)
            raise AssertionError("unsupported fake query operation")

    class FakeDB:
        def __init__(self):
            self.tables = {"customers": [], "transactions": [], "data_import_batches": []}
            self.failure = (failure_table, commit_before_failure)
            self.failed = False

        def table(self, name):
            return FakeQuery(self, name)

    db = FakeDB()
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-only")
    monkeypatch.setitem(sys.modules, "supabase", SimpleNamespace(create_client=lambda *_: db))

    with pytest.raises(RuntimeError, match="injected"):
        import_to_supabase(
            customer_rows, transaction_rows, checksum, "bancabc_core", "USD",
            ["customers.csv", "transactions.csv"], approval,
        )

    batch = db.tables["data_import_batches"][0]
    assert batch["status"] == "partially_loaded"
    assert batch["inserted_row_count"] == (
        len(db.tables["customers"]) + len(db.tables["transactions"])
    )
    original_batch_id = batch["import_batch_id"]
    db.failure = None

    result = import_to_supabase(
        customer_rows, transaction_rows, checksum, "bancabc_core", "USD",
        ["customers.csv", "transactions.csv"], approval, original_batch_id,
    )
    assert result["status"] == "loaded"
    assert result["resumed_existing_batch"] is True
    assert len(db.tables["customers"]) == 1
    assert len(db.tables["transactions"]) == 1
    assert db.tables["customers"][0]["import_batch_id"] == original_batch_id
    assert db.tables["transactions"][0]["import_batch_id"] == original_batch_id
    assert db.tables["data_import_batches"][0]["status"] == "loaded"



def test_select_all_reads_past_default_api_page_limit():
    class Query:
        def __init__(self, rows):
            self.rows = rows
            self.start, self.end = 0, 999

        def select(self, _columns):
            return self

        def eq(self, _field, _value):
            return self

        def range(self, start, end):
            self.start, self.end = start, end
            return self

        def execute(self):
            return type("Result", (), {"data": self.rows[self.start:self.end + 1]})()

    class DB:
        def __init__(self, rows):
            self.rows = rows

        def table(self, _name):
            return Query(self.rows)

    rows = [{"id": i} for i in range(2305)]
    result = _select_all(DB(rows), "transactions", "id", {"import_batch_id": "batch"})
    assert len(result) == 2305
    assert result[0]["id"] == 0
    assert result[-1]["id"] == 2304
