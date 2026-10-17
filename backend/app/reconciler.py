import json

from app.csv_loader import parse_settlement_csv
from app.issues import calculate_status, summarize_settlements
from app.matcher import find_transaction


def reconcile(conn, rows):
    """
    Reconcile validated CSV rows against the database.
    Safe to run repeatedly: settlements already in the database are skipped,
    and totals are always recomputed from settlement_history (never incremented).
    """
    summary = {
        "rows_processed": len(rows),
        "inserted": 0,
        "duplicates_skipped": 0,
        "matched_by_lifecycle_id": 0,
        "matched_by_fallback": 0,
        "exceptions": [],
        "transactions_updated": 0,
    }
    affected = set()

    try:
        for row in rows:
            match = find_transaction(conn, row)

            if match["transaction_id"] is None:
                _add_exception(conn, row, match["method"], match["reason"], summary)
                continue

            txn = conn.execute(
                "SELECT * FROM transactions WHERE transaction_id = ?",
                (match["transaction_id"],),
            ).fetchone()

            if row["currency"] != txn["currency"]:
                reason = (f"Currency mismatch: settlement is {row['currency']}, "
                          f"transaction is {txn['currency']}")
                _add_exception(conn, row, "CURRENCY_MISMATCH", reason, summary)
                continue

            exists = conn.execute(
                "SELECT 1 FROM settlement_history WHERE settlement_id = ?",
                (row["settlement_id"],),
            ).fetchone()
            if exists:
                summary["duplicates_skipped"] += 1
                continue

            conn.execute(
                """INSERT INTO settlement_history
                   (settlement_id, transaction_id, lifecycle_id, settlement_date,
                    settlement_amount, settlement_type, currency)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    row["settlement_id"],
                    txn["transaction_id"],
                    row["lifecycle_id"] or txn["lifecycle_id"],
                    row["settlement_date"].isoformat(),
                    str(row["settlement_amount"]),       
                    row["settlement_type"],
                    row["currency"],
                ),
            )
            summary["inserted"] += 1
            affected.add(txn["transaction_id"])
            if match["method"] == "LIFECYCLE_ID":
                summary["matched_by_lifecycle_id"] += 1
            else:
                summary["matched_by_fallback"] += 1

        for transaction_id in affected:
            refresh_transaction(conn, transaction_id)
        summary["transactions_updated"] = len(affected)

        conn.commit()
    except Exception:
        conn.rollback()
        raise

    return summary


def reconcile_csv(conn, content):
    """Parse + validate CSV text/bytes, then reconcile the valid rows."""
    rows, errors = parse_settlement_csv(content)
    summary = reconcile(conn, rows)
    summary["rejected_rows"] = errors
    return summary


def refresh_transaction(conn, transaction_id):
    """Recompute status, total_settled_amount and last_settlement_date from settlement_history."""
    txn = conn.execute(
        "SELECT * FROM transactions WHERE transaction_id = ?", (transaction_id,)
    ).fetchone()
    settlements = conn.execute(
        "SELECT * FROM settlement_history WHERE transaction_id = ?", (transaction_id,)
    ).fetchall()

    status = calculate_status(txn, settlements)
    totals = summarize_settlements(settlements)
    last_date = totals["last_settlement_date"]

    conn.execute(
        """UPDATE transactions
           SET settlement_status = ?, total_settled_amount = ?, last_settlement_date = ?
           WHERE transaction_id = ?""",
        (status, str(totals["net"]), last_date.isoformat() if last_date else None, transaction_id),
    )


def _add_exception(conn, row, reason_code, detail, summary):
    reason = f"{reason_code}: {detail}" if detail else reason_code
    already = conn.execute(
        "SELECT 1 FROM reconciliation_exceptions WHERE settlement_id = ? AND reason = ?",
        (row["settlement_id"], reason),
    ).fetchone()
    if not already:                                  
        conn.execute(
            "INSERT INTO reconciliation_exceptions (settlement_id, reason, raw_row) VALUES (?, ?, ?)",
            (row["settlement_id"], reason, json.dumps(row, default=str)),
        )
    summary["exceptions"].append({"settlement_id": row["settlement_id"], "reason": reason})