from decimal import Decimal

import pytest

from app.csv_loader import parse_settlement_csv

HEADER = ("settlement_id,lifecycle_id,account_id,merchant_name,transaction_date,"
          "settlement_date,settlement_amount,settlement_type,currency\n")


def parse(*lines):
    return parse_settlement_csv(HEADER + "\n".join(lines) + "\n")


def test_valid_row():
    rows, errors = parse("SET001,LC001,ACC123,Amazon.com,2025-08-14,2025-08-15,125.99,DEBIT,USD")
    assert errors == []
    assert rows[0]["settlement_amount"] == Decimal("125.99")
    assert rows[0]["lifecycle_id"] == "LC001"


def test_blank_lifecycle_id_becomes_none():
    rows, errors = parse("SET014,,ACC135,Corner Deli,2025-08-14,2025-08-15,32.45,DEBIT,USD")
    assert errors == []
    assert rows[0]["lifecycle_id"] is None


def test_negative_amount_rejected():
    rows, errors = parse("SET1,LC1,A,M,2025-08-14,2025-08-15,-5.00,DEBIT,USD")
    assert rows == []
    assert "positive" in errors[0]["errors"][0]


def test_non_numeric_and_nan_amounts_rejected():
    rows, errors = parse(
        "SET1,LC1,A,M,2025-08-14,2025-08-15,abc,DEBIT,USD",
        "SET2,LC1,A,M,2025-08-14,2025-08-15,NaN,DEBIT,USD",
    )
    assert rows == []
    assert len(errors) == 2


def test_bad_type_date_and_currency_rejected():
    _, errors = parse("SET1,LC1,A,M,14/08/2025,2025-08-15,5.00,REFUND,US")
    msgs = " ".join(errors[0]["errors"])
    assert "DEBIT or CREDIT" in msgs
    assert "transaction_date" in msgs
    assert "currency" in msgs


def test_duplicate_settlement_id_in_file():
    rows, errors = parse(
        "SET1,LC1,A,M,2025-08-14,2025-08-15,5.00,DEBIT,USD",
        "SET1,LC1,A,M,2025-08-14,2025-08-15,5.00,DEBIT,USD",
    )
    assert len(rows) == 1
    assert errors[0]["row"] == 3


def test_one_bad_row_does_not_stop_the_rest():
    rows, errors = parse(
        "SET1,LC1,A,M,2025-08-14,2025-08-15,5.00,DEBIT,USD",
        "SET2,LC1,A,M,2025-08-14,2025-08-15,oops,DEBIT,USD",
        "SET3,LC1,A,M,2025-08-14,2025-08-15,7.00,DEBIT,USD",
    )
    assert [r["settlement_id"] for r in rows] == ["SET1", "SET3"]
    assert len(errors) == 1


def test_missing_column_raises():
    with pytest.raises(ValueError):
        parse_settlement_csv("settlement_id,account_id\nSET1,ACC1\n")


def test_empty_file_raises():
    with pytest.raises(ValueError):
        parse_settlement_csv("")