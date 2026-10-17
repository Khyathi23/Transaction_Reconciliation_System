import sqlite3
from datetime import date
from pathlib import Path

import pytest

from app.matcher import find_transaction

SQL_DIR = Path(__file__).resolve().parent.parent / "sql"


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.executescript((SQL_DIR / "schema.sql").read_text(encoding="utf-8"))
    c.executescript((SQL_DIR / "seed.sql").read_text(encoding="utf-8"))
    yield c
    c.close()


def row(lifecycle_id, account, merchant, txn_date="2025-08-14"):
    return {"lifecycle_id": lifecycle_id, "account_id": account,
            "merchant_name": merchant, "transaction_date": date.fromisoformat(txn_date)}


def test_match_by_lifecycle_id(conn):
    r = find_transaction(conn, row("LC001", "ACC123", "Amazon.com"))
    assert r["transaction_id"] == "TXN001"
    assert r["method"] == "LIFECYCLE_ID"


def test_scenario_5_missing_lifecycle_id_uses_fallback(conn):
    r = find_transaction(conn, row(None, "ACC135", "Corner Deli"))
    assert r["transaction_id"] == "TXN013"
    assert r["method"] == "FALLBACK"


def test_unknown_lifecycle_id_falls_back_to_account_match(conn):
    r = find_transaction(conn, row("LC-WRONG", "ACC136", "Shell Gas"))
    assert r["transaction_id"] == "TXN014"
    assert r["method"] == "FALLBACK"


def test_orphan_lifecycle_id_is_unmatched(conn):
    r = find_transaction(conn, row("LC999", "ACC199", "Disney Plus"))     
    assert r["transaction_id"] is None
    assert r["method"] == "UNMATCHED"


def test_orphan_without_lifecycle_id_is_unmatched(conn):
    r = find_transaction(conn, row(None, "ACC777", "Uber Taxi", "2025-08-10"))   
    assert r["method"] == "UNMATCHED"


def test_fallback_to_failed_transaction_still_matches(conn):
    r = find_transaction(conn, row(None, "ACC137", "Amazon.com"))        
    assert r["transaction_id"] == "TXN015"


def test_ambiguous_fallback_is_not_guessed(conn):
    conn.execute(
        "INSERT INTO transactions (transaction_id, lifecycle_id, account_id, merchant_name, "
        "transaction_date, transaction_amount, currency, status) VALUES "
        "('TXN100','LC100','ACC900','Dup Shop','2025-08-14',10.00,'USD','COMPLETED'),"
        "('TXN101','LC101','ACC900','Dup Shop','2025-08-14',10.00,'USD','COMPLETED')"
    )
    r = find_transaction(conn, row(None, "ACC900", "Dup Shop"))
    assert r["transaction_id"] is None
    assert r["method"] == "AMBIGUOUS"