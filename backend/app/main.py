import csv
import io
from datetime import date
from typing import Optional

from fastapi import Depends, FastAPI, File, HTTPException, Query, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from app import metrics
from app.db import BASE_DIR, DB_PATH, get_connection
from app.reconciler import reconcile_csv

DEFAULT_CSV = BASE_DIR.parent / "data" / "settlement_report.csv"

EXPORT_HEADERS = [
    "transaction_id", "date", "merchant_name", "account_id", "amount", "currency",
    "transaction_status", "settlement_status", "settled_amount",
    "last_settlement_date", "issue_flag",
]

app = FastAPI(title="Transaction Reconciliation API")

# Allow the React dev server (Vite) to call this API from the browser
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_db():
    if not DB_PATH.exists():
        raise HTTPException(500, "Database not found. Run: python scripts/seed.py")
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()


def _csv_safe(value):
    """Stop Excel from running text like '=SUM(...)' as a formula."""
    if isinstance(value, str) and value[:1] in ("=", "+", "-", "@"):
        return "'" + value
    return value


@app.get("/")
def root():
    return {"message": "Transaction Reconciliation API", "docs": "/docs"}


@app.post("/reconcile")
def reconcile_endpoint(file: Optional[UploadFile] = File(None), conn=Depends(get_db)):
    """Upload a settlement CSV and reconcile it. With no file, uses data/settlement_report.csv."""
    if file is None or not file.filename:
        if not DEFAULT_CSV.exists():
            raise HTTPException(400, "No file uploaded and default CSV not found")
        content = DEFAULT_CSV.read_bytes()
    else:
        content = file.file.read()

    try:
        return reconcile_csv(conn, content)
    except ValueError as e:                     # empty file, missing columns, bad encoding
        raise HTTPException(400, str(e))


@app.get("/transactions")
def list_transactions(
    status: Optional[str] = Query(None, description="PENDING, PARTIAL, FULLY_SETTLED, OVER_SETTLED, REFUNDED, NOT_APPLICABLE"),
    flag: Optional[str] = Query(None, description="CRITICAL or WARNING"),
    search: Optional[str] = Query(None, description="Matches transaction id, merchant or account"),
    as_of: Optional[date] = Query(None, description="Date for the 7-day rule (YYYY-MM-DD)"),
    conn=Depends(get_db),
):
    return metrics.list_transactions(conn, metrics.resolve_as_of(conn, as_of), status, flag, search)


# Must stay ABOVE /transactions/{transaction_id}, otherwise "export" is read as an id (404)
@app.get("/transactions/export")
def export_transactions(
    status: Optional[str] = Query(None),
    flag: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    as_of: Optional[date] = Query(None),
    conn=Depends(get_db),
):
    """Download the (filtered) transaction list as a CSV file."""
    rows = metrics.list_transactions(conn, metrics.resolve_as_of(conn, as_of), status, flag, search)

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(EXPORT_HEADERS)
    for r in rows:
        writer.writerow([
            _csv_safe(r["transaction_id"]), r["date"], _csv_safe(r["merchant_name"]),
            _csv_safe(r["account_id"]), f"{r['amount']:.2f}", r["currency"],
            r["transaction_status"], r["settlement_status"], f"{r['settled_amount']:.2f}",
            r["last_settlement_date"] or "", r["flag"] or "OK",
        ])

    return Response(
        content=buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="transactions.csv"'},
    )


@app.get("/transactions/{transaction_id}")
def get_transaction(
    transaction_id: str,
    as_of: Optional[date] = Query(None),
    conn=Depends(get_db),
):
    detail = metrics.get_transaction_detail(conn, transaction_id, metrics.resolve_as_of(conn, as_of))
    if detail is None:
        raise HTTPException(404, f"Transaction {transaction_id} not found")
    return detail


@app.get("/dashboard/summary")
def dashboard_summary(as_of: Optional[date] = Query(None), conn=Depends(get_db)):
    return metrics.dashboard_summary(conn, metrics.resolve_as_of(conn, as_of))