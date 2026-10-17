import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app, get_db

BACKEND = Path(__file__).resolve().parent.parent
SQL_DIR = BACKEND / "sql"
CSV_PATH = BACKEND.parent / "data" / "settlement_report.csv"
AS_OF = "2025-08-15"


@pytest.fixture
def client():
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript((SQL_DIR / "schema.sql").read_text(encoding="utf-8"))
    conn.executescript((SQL_DIR / "seed.sql").read_text(encoding="utf-8"))

    app.dependency_overrides[get_db] = lambda: conn
    yield TestClient(app)
    app.dependency_overrides.clear()
    conn.close()


def upload(client, content=None):
    content = CSV_PATH.read_bytes() if content is None else content
    return client.post("/reconcile", files={"file": ("settlement_report.csv", content, "text/csv")})



def test_reconcile_upload(client):
    r = upload(client)
    assert r.status_code == 200
    body = r.json()
    assert body["inserted"] == 17
    assert body["matched_by_fallback"] == 3
    assert {e["settlement_id"] for e in body["exceptions"]} == {"SET016", "SET018"}
    assert body["rejected_rows"] == []


def test_reconcile_without_file_uses_default_csv(client):
    r = client.post("/reconcile")
    assert r.status_code == 200
    assert r.json()["inserted"] == 17


def test_reconcile_rejects_unusable_file(client):
    r = upload(client, b"settlement_id,account_id\nSET1,ACC1\n")
    assert r.status_code == 400
    assert "missing required columns" in r.json()["detail"]


def test_reconcile_twice_does_not_double_count(client):
    upload(client)
    second = upload(client).json()
    assert second["inserted"] == 0
    assert second["duplicates_skipped"] == 17
    assert client.get("/dashboard/summary").json()["total_settlements"] == 17




def test_list_transactions_flags(client):
    upload(client)
    rows = client.get("/transactions", params={"as_of": AS_OF}).json()
    flags = {r["transaction_id"]: r["flag"] for r in rows}
    assert len(rows) == 14
    assert flags["TXN007"] == "CRITICAL"    
    assert flags["TXN010"] == "CRITICAL"     
    assert flags["TXN015"] == "CRITICAL"     
    assert flags["TXN003"] == "WARNING"      
    assert flags["TXN001"] is None
    assert flags["TXN002"] is None           


def test_filter_by_status(client):
    upload(client)
    rows = client.get("/transactions", params={"status": "REFUNDED", "as_of": AS_OF}).json()
    assert {r["transaction_id"] for r in rows} == {"TXN002", "TXN004", "TXN006", "TXN008"}


def test_filter_by_flag(client):
    upload(client)
    rows = client.get("/transactions", params={"flag": "CRITICAL", "as_of": AS_OF}).json()
    assert {r["transaction_id"] for r in rows} == {"TXN007", "TXN010", "TXN015"}



def test_transaction_detail_over_settled(client):
    upload(client)
    d = client.get("/transactions/TXN007", params={"as_of": AS_OF}).json()
    assert d["settlement_status"] == "OVER_SETTLED"
    assert d["flag"] == "CRITICAL"
    assert len(d["settlements"]) == 1
    assert d["issues"][0]["code"] == "OVER_SETTLED"
    assert d["issues"][0]["recommendation"]


def test_transaction_detail_timeline_for_refund(client):
    upload(client)
    d = client.get("/transactions/TXN008", params={"as_of": AS_OF}).json()
    assert d["settlement_status"] == "REFUNDED"
    assert d["totals"]["net"] == 1000.00
    assert [e["running_net"] for e in d["timeline"]] == [1299.99, 1000.00]


def test_transaction_detail_not_found(client):
    assert client.get("/transactions/NOPE").status_code == 404



def test_dashboard_summary_after_reconcile(client):
    upload(client)
    s = client.get("/dashboard/summary", params={"as_of": AS_OF}).json()
    assert s["total_transactions"] == 14
    assert s["total_settlements"] == 17
    assert s["unmatched_exceptions"] == 2
    assert s["status_breakdown"]["FULLY_SETTLED"] == 6
    assert s["status_breakdown"]["REFUNDED"] == 4
    assert s["status_breakdown"]["PARTIAL"] == 1
    assert s["status_breakdown"]["OVER_SETTLED"] == 1
    assert s["status_breakdown"]["PENDING"] == 1
    assert s["critical_issues"] == 3
    assert s["warnings"] == 1
    assert s["total_outstanding_amount"] == 25.99     
    assert s["avg_days_to_settle"] == 1.0
    assert s["settlement_rate"] == 91.67              

def test_dashboard_summary_before_reconcile(client):
    s = client.get("/dashboard/summary").json()
    assert s["total_settlements"] == 0
    assert s["status_breakdown"]["PENDING"] == 12
    assert s["status_breakdown"]["NOT_APPLICABLE"] == 2
    assert s["avg_days_to_settle"] is None