import duckdb
import pandas as pd
from pathlib import Path

DATA_PATH = Path("data/operational_intelligence_transactions_db.csv")
DB_PATH = Path("cloudwalk.db")

def init_db():
    print("🚀 Creating DuckDB database...")

    # The CSV uses semicolons as delimiters, so specify sep=';'
    df = pd.read_csv(DATA_PATH, sep=';')

    # Try to parse a date column if present
    if 'day' in df.columns:
        try:
            df['day'] = pd.to_datetime(df['day'], errors='coerce')
        except Exception:
            pass

    con = duckdb.connect(str(DB_PATH))

    con.execute("DROP TABLE IF EXISTS transactions;")

    con.execute("""
        CREATE TABLE transactions AS
        SELECT * FROM df;
    """)

    con.close()

    print("✅ Database created successfully:", DB_PATH)

if __name__ == "__main__":
    init_db()