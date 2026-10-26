import sqlite3
from pathlib import Path

db = Path(__file__).resolve().parent.parent / "reconciliation.db"
conn = sqlite3.connect(db)
conn.execute(
    "INSERT OR IGNORE INTO settlement_history (settlement_id, transaction_id, lifecycle_id, "
    "settlement_date, settlement_amount, settlement_type, currency) "
    "VALUES ('SETX1', 'TXN002', 'LC002', '2025-08-13', 4.75, 'DEBIT', 'USD')"
)
conn.commit()
print("Added")