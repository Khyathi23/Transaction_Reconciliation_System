def find_transaction(conn, row):
    """
    Match one validated CSV row to a transaction.
    Returns {"transaction_id": str | None, "method": str, "reason": str | None}
    method is one of: LIFECYCLE_ID, FALLBACK, UNMATCHED, AMBIGUOUS
    """
    if row.get("lifecycle_id"):
        found = conn.execute(
            "SELECT transaction_id FROM transactions WHERE lifecycle_id = ?",
            (row["lifecycle_id"],),
        ).fetchall()
        if len(found) == 1:
            return {"transaction_id": found[0]["transaction_id"],
                    "method": "LIFECYCLE_ID", "reason": None}
        if len(found) > 1:
            return {"transaction_id": None, "method": "AMBIGUOUS",
                    "reason": f"lifecycle_id {row['lifecycle_id']} matches {len(found)} transactions"}
    
    found = conn.execute(
        """SELECT transaction_id FROM transactions
           WHERE account_id = ? AND merchant_name = ? AND transaction_date = ?""",
        (row["account_id"], row["merchant_name"], row["transaction_date"].isoformat()),
    ).fetchall()

    if len(found) == 1:
        return {"transaction_id": found[0]["transaction_id"],
                "method": "FALLBACK", "reason": None}
    if len(found) > 1:
        return {"transaction_id": None, "method": "AMBIGUOUS",
                "reason": f"account/merchant/date matches {len(found)} transactions"}
    return {"transaction_id": None, "method": "UNMATCHED",
            "reason": "No transaction found by lifecycle_id or account/merchant/date"}