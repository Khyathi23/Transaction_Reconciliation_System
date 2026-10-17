import sqlite3
from pathlib import Path

import pytest

from app.csv_loader import parse_settlement_csv
from app.issues import to_decimal
from app.reconciler import reconcile, reconcile_csv

BACKEND = Path(__file__).resolve().parent.parent
SQL_DIR = BACKEND / "sql"
CSV_PATH = BACKEND.parent / "data" / "settlement_report.csv"

HEADER = ("settlement_id,lifecycle_id,account_id,merchant_name,transaction_date,"
          "settlement_date,settlement_amount,settlement_type,currency\n")


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    c.executescript((SQL_DIR / "schema.sql").read_text(encoding="utf-8"))
    c.executescript((SQL_DIR / "seed.sql").read_text(encoding="utf-8"))
    yield c
    c.close()


def get(conn, transaction_id):
    return conn.execute(
        "SELECT * FROM transactions WHERE transaction_id = ?", (transaction_id,)
    ).fetchone()


def test_sample_csv_summary_counts(conn):
    result = reconcile_csv(conn, CSV_PATH.read_bytes())
    assert result["rows_processed"] == 19
    assert result["inserted"] == 17
    assert result["matched_by_fallback"] == 3          
    assert len(result["exceptions"]) == 2              
    assert result["rejected_rows"] == []


def test_sample_csv_statuses_and_totals(conn):
    reconcile_csv(conn, CSV_PATH.read_bytes())
    expected = {
        "TXN001": ("FULLY_SETTLED", "125.99"),
        "TXN002": ("REFUNDED", "3.25"),
        "TXN003": ("PARTIAL", "35.30"),
        "TXN004": ("REFUNDED", "879.99"),
        "TXN005": ("FULLY_SETTLED", "234.50"),
        "TXN006": ("REFUNDED", "75.00"),
        "TXN007": ("OVER_SETTLED", "180.78"),
        "TXN008": ("REFUNDED", "1000.00"),
        "TXN009": ("FULLY_SETTLED", "189.95"),
        "TXN010": ("PENDING", "0.00"),
        "TXN013": ("FULLY_SETTLED", "32.45"),
        "TXN014": ("FULLY_SETTLED", "28.90"),
        "TXN016": ("NOT_APPLICABLE", "0.00"),
    }
    for transaction_id, (status, total) in expected.items():
        t = get(conn, transaction_id)
        assert t["settlement_status"] == status, transaction_id
        assert to_decimal(t["total_settled_amount"]) == to_decimal(total), transaction_id


def test_sample_csv_orphans_go_to_exceptions(conn):
    reconcile_csv(conn, CSV_PATH.read_bytes())
    ids = {r["settlement_id"] for r in conn.execute("SELECT settlement_id FROM reconciliation_exceptions")}
    assert ids == {"SET016", "SET018"}
    assert conn.execute("SELECT COUNT(*) FROM settlement_history").fetchone()[0] == 17


def test_reupload_is_idempotent(conn):
    content = CSV_PATH.read_bytes()
    reconcile_csv(conn, content)
    before = [tuple(r) for r in conn.execute(
        "SELECT transaction_id, settlement_status, total_settled_amount FROM transactions ORDER BY 1")]

    second = reconcile_csv(conn, content)

    after = [tuple(r) for r in conn.execute(
        "SELECT transaction_id, settlement_status, total_settled_amount FROM transactions ORDER BY 1")]
    assert second["inserted"] == 0
    assert second["duplicates_skipped"] == 17
    assert before == after
    assert conn.execute("SELECT COUNT(*) FROM settlement_history").fetchone()[0] == 17
    assert conn.execute("SELECT COUNT(*) FROM reconciliation_exceptions").fetchone()[0] == 2


def test_scenario_6_status_transitions(conn):
    conn.execute(
        "INSERT INTO transactions (transaction_id, lifecycle_id, account_id, merchant_name, "
        "transaction_date, transaction_amount, currency, status) VALUES "
        "('TXN200','LC200','ACC200','Test Shop','2025-08-14',100.00,'USD','COMPLETED')"
    )
    first = HEADER + "S200A,LC200,ACC200,Test Shop,2025-08-14,2025-08-15,50.00,DEBIT,USD\n"
    second = HEADER + "S200B,LC200,ACC200,Test Shop,2025-08-14,2025-08-16,50.00,DEBIT,USD\n"

    reconcile_csv(conn, first)
    t = get(conn, "TXN200")
    assert t["settlement_status"] == "PARTIAL"
    assert to_decimal(t["total_settled_amount"]) == to_decimal("50.00")

    reconcile_csv(conn, second)
    t = get(conn, "TXN200")
    assert t["settlement_status"] == "FULLY_SETTLED"
    assert to_decimal(t["total_settled_amount"]) == to_decimal("100.00")


def test_currency_mismatch_goes_to_exceptions(conn):
    content = HEADER + "SEUR,LC001,ACC123,Amazon.com,2025-08-14,2025-08-15,125.99,DEBIT,EUR\n"
    result = reconcile_csv(conn, content)
    assert result["inserted"] == 0
    assert "CURRENCY_MISMATCH" in result["exceptions"][0]["reason"]
    assert get(conn, "TXN001")["settlement_status"] == "PENDING"


def test_last_settlement_date_is_most_recent(conn):
    reconcile_csv(conn, CSV_PATH.read_bytes())
    assert get(conn, "TXN008")["last_settlement_date"] == "2025-08-08"   
    assert get(conn, "TXN010")["last_settlement_date"] is None