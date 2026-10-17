import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent   
DB_PATH = BASE_DIR / "reconciliation.db"


def get_connection(db_path=DB_PATH):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row          
    conn.execute("PRAGMA foreign_keys = ON")
    return conn