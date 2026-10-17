from datetime import date
from decimal import Decimal

from app.issues import calculate_status, detect_issues, summarize_settlements

AS_OF = date(2025, 8, 15)


def txn(amount="100.00", txn_date="2025-08-14", status="COMPLETED"):
    return {"transaction_amount": amount, "transaction_date": txn_date, "status": status}


def st(amount, kind="DEBIT", when="2025-08-15"):
    return {"settlement_amount": amount, "settlement_type": kind, "settlement_date": when}

def test_scenario_1_perfect_match():
    r = detect_issues(txn(), [st("100.00")], AS_OF)
    assert r["status"] == "FULLY_SETTLED"
    assert r["flag"] is None


def test_scenario_2_partial_settlement_warning():
    r = detect_issues(txn(), [st("80.00")], AS_OF)
    assert r["status"] == "PARTIAL"
    assert r["flag"] == "WARNING"


def test_scenario_3_debit_plus_refund_no_issue():
    r = detect_issues(txn(), [st("100.00"), st("20.00", "CREDIT")], AS_OF)
    assert summarize_settlements([st("100.00"), st("20.00", "CREDIT")])["net"] == Decimal("80.00")
    assert r["flag"] is None


def test_scenario_4_over_settled_critical():
    r = detect_issues(txn(), [st("120.00")], AS_OF)
    assert r["status"] == "OVER_SETTLED"
    assert r["flag"] == "CRITICAL"


def test_scenario_6_status_transitions():
    t = txn()
    assert calculate_status(t, []) == "PENDING"
    assert calculate_status(t, [st("50.00")]) == "PARTIAL"
    assert calculate_status(t, [st("50.00"), st("50.00")]) == "FULLY_SETTLED"


def test_scenario_7_complex_refund():
    settlements = [st("100.00"), st("30.00", "CREDIT")]
    r = detect_issues(txn(), settlements, AS_OF)
    assert summarize_settlements(settlements)["net"] == Decimal("70.00")
    assert r["status"] == "REFUNDED"
    assert r["flag"] is None

def test_no_settlement_within_7_days_is_pending_no_flag():
    r = detect_issues(txn(txn_date="2025-08-14"), [], AS_OF)
    assert r["status"] == "PENDING"
    assert r["flag"] is None


def test_no_settlement_after_7_days_is_critical():
    r = detect_issues(txn(txn_date="2025-08-07"), [], AS_OF)  
    assert r["status"] == "PENDING"
    assert r["flag"] == "CRITICAL"


def test_exactly_7_days_is_not_flagged():
    r = detect_issues(txn(txn_date="2025-08-08"), [], AS_OF)  
    assert r["flag"] is None


def test_failed_transaction_without_settlement_is_fine():
    r = detect_issues(txn(status="FAILED"), [], AS_OF)
    assert r["status"] == "NOT_APPLICABLE"
    assert r["flag"] is None


def test_failed_transaction_with_settlement_is_critical():
    r = detect_issues(txn(status="FAILED"), [st("100.00")], AS_OF)
    assert r["flag"] == "CRITICAL"
    assert r["issues"][0]["code"] == "SETTLEMENT_ON_FAILED_TRANSACTION"


def test_two_debits_sum_exactly_to_amount():
    t = txn(amount="234.50")
    assert calculate_status(t, [st("150.00"), st("84.50")]) == "FULLY_SETTLED"