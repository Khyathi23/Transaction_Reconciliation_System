import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent   
DB_PATH = BASE_DIR / "reconciliation.db"
SQL_DIR = BASE_DIR / "sql"


def seed(db_path=DB_PATH):
    db_path = Path(db_path)
    if db_path.exists():
        db_path.unlink()                     

    conn = sqlite3.connect(db_path)
    try:
        conn.executescript((SQL_DIR / "schema.sql").read_text(encoding="utf-8"))
        conn.executescript((SQL_DIR / "seed.sql").read_text(encoding="utf-8"))
        conn.commit()

        count = conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
        print(f"Database created at {db_path}")
        print(f"Transactions loaded: {count}")
    finally:
        conn.close()


if __name__ == "__main__":
    seed()