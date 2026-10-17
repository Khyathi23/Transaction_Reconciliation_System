from datetime import date
from typing import Optional

from fastapi import Depends, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from app import metrics
from app.db import BASE_DIR, DB_PATH, get_connection
from app.reconciler import reconcile_csv

DEFAULT_CSV = BASE_DIR.parent / "data" / "settlement_report.csv"

app = FastAPI(title="Transaction Reconciliation API")

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
    except ValueError as e:                    
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