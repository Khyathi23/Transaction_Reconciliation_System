from datetime import date, datetime
from decimal import Decimal

CENT = Decimal("0.01")
OVERDUE_DAYS = 7          # "no settlement after 7 days" means more than 7 days


def to_decimal(value) -> Decimal:
    """Convert to a 2-decimal Decimal. Never use floats for money."""
    return Decimal(str(value)).quantize(CENT)


def to_date(value) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def summarize_settlements(settlements):
    """Totals for a list of settlements (dicts or sqlite3.Row)."""
    debits = Decimal("0.00")
    credits = Decimal("0.00")
    last_date = None

    for s in settlements:
        amount = to_decimal(s["settlement_amount"])
        if s["settlement_type"] == "DEBIT":
            debits += amount
        else:
            credits += amount
        d = to_date(s["settlement_date"])
        if last_date is None or d > last_date:
            last_date = d

    return {
        "debits": debits,
        "credits": credits,
        "net": debits - credits,
        "count": len(settlements),
        "last_settlement_date": last_date,
    }


def calculate_status(transaction, settlements):
    """PENDING / PARTIAL / FULLY_SETTLED / OVER_SETTLED / REFUNDED / NOT_APPLICABLE."""
    if transaction["status"] != "COMPLETED" and not settlements:
        return "NOT_APPLICABLE"
    if not settlements:
        return "PENDING"

    amount = to_decimal(transaction["transaction_amount"])
    t = summarize_settlements(settlements)

    if t["net"] > amount:
        return "OVER_SETTLED"
    if t["net"] == amount:
        return "FULLY_SETTLED"
    # net < amount
    if t["credits"] > 0 and t["debits"] >= amount:
        return "REFUNDED"      # fully charged, then money was given back
    return "PARTIAL"


def detect_issues(transaction, settlements, as_of):
    """
    Returns {"status", "flag", "issues"}.
    flag is "CRITICAL", "WARNING" or None.
    as_of is the date used for the 7-day rule (pass it in, don't use today's clock).
    """
    as_of = to_date(as_of)
    status = calculate_status(transaction, settlements)
    amount = to_decimal(transaction["transaction_amount"])
    t = summarize_settlements(settlements)
    issues = []

    if transaction["status"] != "COMPLETED":
        # FAILED / DECLINED transactions must never have settlements
        if settlements:
            issues.append({
                "severity": "CRITICAL",
                "code": "SETTLEMENT_ON_FAILED_TRANSACTION",
                "message": f"Transaction is {transaction['status']} but has settlements.",
                "recommendation": "Investigate and reverse or refund the settlement.",
            })
    else:
        if status == "OVER_SETTLED":
            excess = t["net"] - amount
            issues.append({
                "severity": "CRITICAL",
                "code": "OVER_SETTLED",
                "message": f"Net settled {t['net']} exceeds transaction amount {amount} by {excess}.",
                "recommendation": f"Refund or reverse the excess {excess}.",
            })
        elif status == "PENDING":
            days = (as_of - to_date(transaction["transaction_date"])).days
            if days > OVERDUE_DAYS:
                issues.append({
                    "severity": "CRITICAL",
                    "code": "NO_SETTLEMENT_OVERDUE",
                    "message": f"No settlement received {days} days after the transaction.",
                    "recommendation": "Contact the acquirer or merchant about the missing settlement.",
                })
        elif status == "PARTIAL":
            missing = amount - t["net"]
            issues.append({
                "severity": "WARNING",
                "code": "PARTIALLY_SETTLED",
                "message": f"Net settled {t['net']} is less than {amount}. {missing} outstanding.",
                "recommendation": f"Follow up on the remaining {missing}.",
            })
        # FULLY_SETTLED and REFUNDED are intentionally not flagged

    # Warning: any settlement dated before the transaction itself
    txn_date = to_date(transaction["transaction_date"])
    early = [to_date(s["settlement_date"]) for s in settlements
             if to_date(s["settlement_date"]) < txn_date]
    if early:
        issues.append({
            "severity": "WARNING",
            "code": "SETTLEMENT_BEFORE_TRANSACTION",
            "message": f"{len(early)} settlement(s) dated before the transaction date "
                       f"{txn_date} (earliest {min(early)}).",
            "recommendation": "Check the settlement and transaction dates for a data entry "
                              "or timezone error, and confirm with the acquirer.",
        })

    if any(i["severity"] == "CRITICAL" for i in issues):
        flag = "CRITICAL"
    elif issues:
        flag = "WARNING"
    else:
        flag = None

    return {"status": status, "flag": flag, "issues": issues}