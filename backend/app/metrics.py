import os
from collections import Counter, defaultdict

from app.issues import detect_issues, summarize_settlements, to_date, to_decimal

STATUSES = ["PENDING", "PARTIAL", "FULLY_SETTLED", "OVER_SETTLED", "REFUNDED", "NOT_APPLICABLE"]


def resolve_as_of(conn, as_of=None):
    """
    The date used for the 7-day rule. Priority:
    1. ?as_of=YYYY-MM-DD query parameter
    2. AS_OF_DATE environment variable
    3. the latest date found in the data (so old sample data isn't all flagged overdue)
    """
    if as_of:
        return to_date(as_of)
    env = os.getenv("AS_OF_DATE")
    if env:
        return to_date(env)
    row = conn.execute(
        """SELECT MAX(d) FROM (
               SELECT MAX(transaction_date) AS d FROM transactions
               UNION ALL
               SELECT MAX(settlement_date) AS d FROM settlement_history)"""
    ).fetchone()
    return to_date(row[0]) if row and row[0] else to_date("1970-01-01")


def _load(conn):
    transactions = conn.execute("SELECT * FROM transactions ORDER BY transaction_id").fetchall()
    grouped = defaultdict(list)
    for s in conn.execute("SELECT * FROM settlement_history ORDER BY settlement_date, settlement_id"):
        grouped[s["transaction_id"]].append(s)
    return transactions, grouped


def _list_row(txn, settlements, as_of):
    result = detect_issues(txn, settlements, as_of)
    totals = summarize_settlements(settlements)
    return {
        "transaction_id": txn["transaction_id"],
        "lifecycle_id": txn["lifecycle_id"],
        "account_id": txn["account_id"],
        "date": txn["transaction_date"],
        "merchant_name": txn["merchant_name"],
        "amount": float(to_decimal(txn["transaction_amount"])),
        "currency": txn["currency"],
        "transaction_status": txn["status"],
        "settlement_status": result["status"],
        "settled_amount": float(totals["net"]),
        "last_settlement_date": totals["last_settlement_date"].isoformat()
        if totals["last_settlement_date"] else None,
        "flag": result["flag"],
        "issue_count": len(result["issues"]),
    }


def list_transactions(conn, as_of, status=None, flag=None, search=None):
    transactions, grouped = _load(conn)
    rows = [_list_row(t, grouped[t["transaction_id"]], as_of) for t in transactions]

    if status:
        rows = [r for r in rows if r["settlement_status"] == status.upper()]
    if flag:
        rows = [r for r in rows if r["flag"] == flag.upper()]
    if search:
        q = search.lower()
        rows = [r for r in rows if q in r["transaction_id"].lower()
                or q in r["merchant_name"].lower() or q in r["account_id"].lower()]
    return rows


def get_transaction_detail(conn, transaction_id, as_of):
    txn = conn.execute(
        "SELECT * FROM transactions WHERE transaction_id = ?", (transaction_id,)
    ).fetchone()
    if txn is None:
        return None

    settlements = conn.execute(
        "SELECT * FROM settlement_history WHERE transaction_id = ? ORDER BY settlement_date, settlement_id",
        (transaction_id,),
    ).fetchall()

    result = detect_issues(txn, settlements, as_of)
    totals = summarize_settlements(settlements)

    timeline, running = [], to_decimal("0")
    for s in settlements:
        amount = to_decimal(s["settlement_amount"])
        running += amount if s["settlement_type"] == "DEBIT" else -amount
        timeline.append({
            "settlement_id": s["settlement_id"],
            "date": s["settlement_date"],
            "type": s["settlement_type"],
            "amount": float(amount),
            "running_net": float(running),
        })

    return {
        "transaction": {
            "transaction_id": txn["transaction_id"],
            "lifecycle_id": txn["lifecycle_id"],
            "account_id": txn["account_id"],
            "merchant_name": txn["merchant_name"],
            "transaction_date": txn["transaction_date"],
            "amount": float(to_decimal(txn["transaction_amount"])),
            "currency": txn["currency"],
            "transaction_status": txn["status"],
        },
        "settlement_status": result["status"],
        "flag": result["flag"],
        "issues": result["issues"],
        "totals": {
            "debits": float(totals["debits"]),
            "credits": float(totals["credits"]),
            "net": float(totals["net"]),
        },
        "settlements": [
            {
                "settlement_id": s["settlement_id"],
                "settlement_date": s["settlement_date"],
                "settlement_amount": float(to_decimal(s["settlement_amount"])),
                "settlement_type": s["settlement_type"],
                "currency": s["currency"],
            }
            for s in settlements
        ],
        "timeline": timeline,
        "as_of": as_of.isoformat(),
    }


def dashboard_summary(conn, as_of):
    transactions, grouped = _load(conn)

    status_counts = Counter({s: 0 for s in STATUSES})
    issue_codes = Counter()
    critical = warning = 0
    outstanding = to_decimal("0")
    days_to_settle = []
    eligible = settled_any = 0

    for t in transactions:
        settlements = grouped[t["transaction_id"]]
        result = detect_issues(t, settlements, as_of)
        status_counts[result["status"]] += 1

        if result["flag"] == "CRITICAL":
            critical += 1
        elif result["flag"] == "WARNING":
            warning += 1
        for issue in result["issues"]:
            issue_codes[issue["code"]] += 1

        if t["status"] != "COMPLETED":
            continue
        eligible += 1
        if settlements:
            settled_any += 1
            first = to_date(settlements[0]["settlement_date"])   
            days_to_settle.append((first - to_date(t["transaction_date"])).days)
        if result["status"] in ("PENDING", "PARTIAL"):
            net = summarize_settlements(settlements)["net"]
            outstanding += to_decimal(t["transaction_amount"]) - net

    total_settlements = sum(len(v) for v in grouped.values())
    exceptions = conn.execute("SELECT COUNT(*) FROM reconciliation_exceptions").fetchone()[0]

    return {
        "as_of": as_of.isoformat(),
        "total_transactions": len(transactions),
        "total_settlements": total_settlements,
        "unmatched_exceptions": exceptions,
        "status_breakdown": dict(status_counts),
        "critical_issues": critical,
        "warnings": warning,
        "issues_by_type": dict(issue_codes),
        "total_outstanding_amount": float(outstanding),
        "avg_days_to_settle": round(sum(days_to_settle) / len(days_to_settle), 2)
        if days_to_settle else None,
        "settlement_rate": round(settled_any / eligible * 100, 2) if eligible else 0.0,
    }

def merchant_summary(conn, as_of):
    transactions, grouped = _load(conn)
    merchants = {}

    for t in transactions:
        settlements = grouped[t["transaction_id"]]
        result = detect_issues(t, settlements, as_of)
        net = summarize_settlements(settlements)["net"]
        amount = to_decimal(t["transaction_amount"])

        m = merchants.setdefault(t["merchant_name"], {
            "merchant_name": t["merchant_name"],
            "transaction_count": 0,
            "total_transaction_amount": to_decimal("0"),
            "total_net_settled": to_decimal("0"),
            "outstanding_amount": to_decimal("0"),
            "critical_issue_count": 0,
        })
        m["transaction_count"] += 1
        m["total_transaction_amount"] += amount
        m["total_net_settled"] += net
        # same definition of outstanding as the dashboard summary
        if t["status"] == "COMPLETED" and result["status"] in ("PENDING", "PARTIAL"):
            m["outstanding_amount"] += max(amount - net, 0)
        if result["flag"] == "CRITICAL":
            m["critical_issue_count"] += 1

    rows = sorted(merchants.values(),
                  key=lambda m: (-m["outstanding_amount"], m["merchant_name"]))
    for m in rows:
        for key in ("total_transaction_amount", "total_net_settled", "outstanding_amount"):
            m[key] = float(m[key])
    return rows