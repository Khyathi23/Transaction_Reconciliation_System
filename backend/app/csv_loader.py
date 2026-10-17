import csv
import io
from datetime import date
from decimal import Decimal, InvalidOperation

COLUMNS = [
    "settlement_id", "lifecycle_id", "account_id", "merchant_name",
    "transaction_date", "settlement_date", "settlement_amount",
    "settlement_type", "currency",
]
REQUIRED_VALUES = [c for c in COLUMNS if c != "lifecycle_id"]   
VALID_TYPES = {"DEBIT", "CREDIT"}


def parse_settlement_csv(content):
    """
    Parse and validate CSV text (or bytes).
    Returns (valid_rows, errors).
      valid_rows: list of clean dicts (amount is a Decimal, dates are date objects)
      errors:     list of {"row", "settlement_id", "errors": [..]}
    Raises ValueError only if the file itself is unusable (empty / missing columns).
    One bad row never stops the rest of the file.
    """
    if isinstance(content, bytes):
        content = content.decode("utf-8-sig")        

    reader = csv.DictReader(io.StringIO(content), restkey="_extra")
    if reader.fieldnames is None:
        raise ValueError("CSV file is empty")
    reader.fieldnames = [h.strip() for h in reader.fieldnames]

    missing = [c for c in COLUMNS if c not in reader.fieldnames]
    if missing:
        raise ValueError(f"CSV is missing required columns: {', '.join(missing)}")

    valid_rows, errors, seen_ids = [], [], set()

    for row_number, raw in enumerate(reader, start=2):     
        if all((v or "").strip() == "" for k, v in raw.items() if k != "_extra"):
            continue                                        

        row = {c: (raw.get(c) or "").strip() for c in COLUMNS}
        problems = []

        if "_extra" in raw:
            problems.append("Row has more columns than the header")

        for col in REQUIRED_VALUES:
            if not row[col]:
                problems.append(f"{col} is missing")

        sid = row["settlement_id"]
        if sid:
            if sid in seen_ids:
                problems.append(f"Duplicate settlement_id {sid} in file")
            seen_ids.add(sid)

        
        amount = None
        if row["settlement_amount"]:
            try:
                amount = Decimal(row["settlement_amount"])
                if not amount.is_finite():
                    raise InvalidOperation
                if amount <= 0:
                    problems.append("settlement_amount must be positive")
                amount = amount.quantize(Decimal("0.01"))
            except InvalidOperation:
                problems.append(f"settlement_amount '{row['settlement_amount']}' is not a number")
                amount = None

       
        stype = row["settlement_type"].upper()
        if row["settlement_type"] and stype not in VALID_TYPES:
            problems.append("settlement_type must be DEBIT or CREDIT")

        
        currency = row["currency"].upper()
        if row["currency"] and not (len(currency) == 3 and currency.isalpha()):
            problems.append("currency must be a 3-letter code")

    
        txn_date = _parse_date(row["transaction_date"], "transaction_date", problems)
        set_date = _parse_date(row["settlement_date"], "settlement_date", problems)
        if txn_date and set_date and set_date < txn_date:
            problems.append("settlement_date is before transaction_date")

        if problems:
            errors.append({"row": row_number, "settlement_id": sid or None, "errors": problems})
            continue

        valid_rows.append({
            "row": row_number,
            "settlement_id": sid,
            "lifecycle_id": row["lifecycle_id"] or None,    
            "account_id": row["account_id"],
            "merchant_name": row["merchant_name"],
            "transaction_date": txn_date,
            "settlement_date": set_date,
            "settlement_amount": amount,
            "settlement_type": stype,
            "currency": currency,
        })

    return valid_rows, errors


def load_csv_file(path):
    with open(path, "rb") as f:
        return parse_settlement_csv(f.read())


def _parse_date(value, name, problems):
    if not value:
        return None                   
    try:
        return date.fromisoformat(value)
    except ValueError:
        problems.append(f"{name} '{value}' is not a valid YYYY-MM-DD date")
        return None