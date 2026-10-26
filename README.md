# Transaction Reconciliation System

Matches transaction records against settlement data, flags discrepancies, and shows the results in a dashboard for finance operations teams.

**Stack:** Python (FastAPI) · SQLite · React (Vite) + Recharts · pytest

## Setup

### Prerequisites
- Python 3.10+
- Node.js 18+

### Backend
```bash
cd backend
python -m venv venv
venv\Scripts\activate            # macOS/Linux: source venv/bin/activate
pip install -r requirements.txt
python scripts/seed.py           # builds reconciliation.db from sql/schema.sql and sql/seed.sql
uvicorn app.main:app --reload    # http://127.0.0.1:8000  (Swagger docs at /docs)
```

### Frontend
```bash
cd frontend
npm install
npm run dev                      # http://localhost:5173
```

### Using the app
1. Open http://localhost:5173
2. On the dashboard click **Reconcile** (leave the file empty to use `data/settlement_report.csv`, or upload your own CSV)
3. Browse **Transactions**, filter by status or issue level, search, export to CSV, and click a row for details

To reset all data: `python scripts/seed.py` (stop the backend first on Windows).

### Tests
```bash
cd backend
python -m pytest -v
```

## Demo: settlement dated before the transaction

The sample CSV has no such row, so a helper script creates the test data.

**Terminal 1: backend**
```bash
cd backend
venv\Scripts\activate            # macOS/Linux: source venv/bin/activate
python scripts/seed.py           # resets the database
uvicorn app.main:app --reload
```

**Terminal 2: frontend**
```bash
cd frontend
npm run dev
```

1. Open http://localhost:5173 and click **Reconcile** (leave the file empty).
2. In a third terminal, from `backend` with the venv active, run:
```bash
curl.exe http://127.0.0.1:8000/dashboard/summary          # "warnings": 1
python scripts/make_early.py                              # moves SET001 to 2025-08-13
curl.exe -s http://127.0.0.1:8000/transactions/TXN001     # flag WARNING + SETTLEMENT_BEFORE_TRANSACTION
curl.exe http://127.0.0.1:8000/dashboard/summary          # "warnings": 2
```
3. Refresh the browser. The Warnings card shows 2, TXN001 has a yellow badge, and its detail page shows the issue and recommendation.

`make_early.py` only changes a date, so the amounts still match and the flag is WARNING, not critical. Run `python scripts/seed.py` to reset. On macOS/Linux use `curl` instead of `curl.exe`.

## Architecture

```
backend/app/
  csv_loader.py   Parse and validate the CSV (row-level errors, Decimal amounts)
  matcher.py      Match a row to a transaction: lifecycle_id first, then account+merchant+date
  issues.py       Pure business rules: net totals, status, critical/warning detection
  reconciler.py   Orchestration: insert settlements, log exceptions, recompute transaction totals
  metrics.py      Dashboard summary and transaction list/detail queries
  main.py         FastAPI routes
  db.py           SQLite connection helper
backend/sql/      schema.sql, seed.sql
backend/scripts/  seed.py, make_early.py (demo data)
backend/tests/    Unit and API integration tests
frontend/src/     React app (Dashboard, TransactionList, TransactionDetail)
data/             settlement_report.csv (sample)
```

**Approach**
- Business rules in `issues.py` are pure functions with no database access, so they are easy to unit test.
- Transaction totals and status are **recomputed from `settlement_history`** after each reconcile instead of being incremented. Re-uploading the same CSV is therefore idempotent.
- Money uses Python `Decimal` throughout, never floats.
- One bad CSV row never stops the file. Each rejected row is reported with its row number.

## API

Interactive docs: http://127.0.0.1:8000/docs

| Method | Endpoint | Description |
|---|---|---|
| POST | `/reconcile` | Upload a CSV (multipart field `file`) and reconcile it. With no file, uses `data/settlement_report.csv`. |
| GET | `/transactions` | List transactions with issue flags. Query: `status`, `flag`, `search`, `as_of`. |
| GET | `/transactions/export` | Download the (filtered) transaction list as CSV. Same query parameters as `/transactions`. |
| GET | `/transactions/{id}` | Transaction details, settlements, issues with recommendations, and timeline. |
| GET | `/dashboard/summary` | Totals, status breakdown, issue counts, outstanding amount, performance metrics. |

**POST /reconcile response**
```json
{
  "rows_processed": 19, "inserted": 17, "duplicates_skipped": 0,
  "matched_by_lifecycle_id": 14, "matched_by_fallback": 3,
  "exceptions": [{"settlement_id": "SET016", "reason": "UNMATCHED: ..."}],
  "transactions_updated": 12, "rejected_rows": []
}
```
Errors: `400` for an unusable file (empty, missing columns), `404` for an unknown transaction id.

## Business rules and assumptions

**Net settlement** = sum of DEBITs minus sum of CREDITs.

| Status | Rule |
|---|---|
| PENDING | No settlements |
| PARTIAL | Net < amount, and not a refund case |
| FULLY_SETTLED | Net = amount |
| OVER_SETTLED | Net > amount |
| REFUNDED | Net < amount, credits exist, and debits >= amount (fully charged, then refunded) |
| NOT_APPLICABLE | Transaction is FAILED or DECLINED with no settlements |

**Issues**
- **Critical:** over-settled; no settlement more than 7 days after the transaction date; any settlement on a FAILED or DECLINED transaction.
- **Warning:** PARTIAL; any settlement dated before its transaction date (`SETTLEMENT_BEFORE_TRANSACTION`).
- REFUNDED is **not** flagged, because scenarios 3 and 7 in the brief expect no issue for refunds.

**Assumptions**
1. **As-of date.** The 7-day rule needs a "today". Sample data is from August 2025, so the real clock would flag everything. The date comes from `?as_of=YYYY-MM-DD`, then the `AS_OF_DATE` environment variable, then the latest date in the data. The dashboard shows the date used.
2. "No settlement after 7 days" means **more than** 7 days (exactly 7 is not flagged).
3. **Matching.** If `lifecycle_id` is missing, or is not found, the fallback (account + merchant + date) is tried. If a match is not unique it is treated as ambiguous and sent to exceptions, never guessed.
4. **Unmatched rows** (orphans: SET016, SET018) are stored in `reconciliation_exceptions`, not in `settlement_history`.
5. **Currency mismatch** between a settlement and its transaction sends the row to exceptions.
6. **Settlement on a failed transaction** (SET017 on TXN015) is stored, so its stored status becomes FULLY_SETTLED, but it is flagged Critical by the issue detector.
7. **Outstanding amount** = unsettled part of COMPLETED transactions that are PENDING or PARTIAL. Refunded and over-settled transactions are not counted.
8. **Settlement rate** = COMPLETED transactions with at least one settlement ÷ all COMPLETED transactions.
9. **Avg days to settle** = first settlement date minus transaction date.
10. Duplicate `settlement_id`s (within a file or already in the database) are skipped.
11. A `reconciliation_exceptions` table was added to the provided schema.
12. A settlement dated before its transaction is flagged as a Warning, not Critical: it is suspicious (likely a data entry or timezone error) but the amounts may still be correct.

## Testing

49 tests: unit tests for status and issue rules (all 7 scenarios from the brief), CSV validation, matching, reconciliation (including idempotency and status transitions), and integration tests for all endpoints (including CSV export and the settlement-before-transaction warning) using an in-memory SQLite database.

## Known limitations
- No authentication or user management.
- Whole database is read into memory for list and summary views. Fine for thousands of rows, not millions. Would need SQL aggregation and pagination at scale.
- Only same-currency reconciliation. No currency conversion.
- Settlements are never updated or deleted by a re-upload. A corrected settlement with the same ID is ignored.
- SQLite is single-writer, so concurrent uploads are serialized.
- CSV export only (no PDF).
- The CSV loader rejects rows whose settlement date is before their transaction date, so `SETTLEMENT_BEFORE_TRANSACTION` only appears for data that reaches the database another way. Accepting and flagging those rows from uploads would be a possible follow-up.
- A settlement dated before its transaction gives a negative "days to settle", which lowers the average days metric. Excluding negative values would be a possible follow-up.
- Frontend has no automated tests.