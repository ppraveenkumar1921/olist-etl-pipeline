import re
import sqlite3

import pandas as pd

from src.load import DB_PATH
from src.utils import BASE_DIR, get_logger

logger = get_logger(__name__)

QUERIES_PATH = BASE_DIR / "sql" / "analysis_queries.sql"
OUTPUT_DIR = BASE_DIR / "docs" / "analysis"


def load_queries() -> dict:
    """Split the SQL file into {query_name: sql} using the '-- name:' markers."""
    text = QUERIES_PATH.read_text(encoding="utf-8")
    parts = re.split(r"^-- name:\s*(\w+)\s*$", text, flags=re.MULTILINE)
    # parts = [preamble, name1, sql1, name2, sql2, ...]
    return {parts[i]: parts[i + 1].strip() for i in range(1, len(parts), 2)}


def run_analysis() -> dict:
    queries = load_queries()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    results = {}
    conn = sqlite3.connect(DB_PATH)
    try:
        for name, sql in queries.items():
            df = pd.read_sql_query(sql, conn)
            df.to_csv(OUTPUT_DIR / f"{name}.csv", index=False)
            logger.info("Ran query %-34s rows=%d", name, len(df))
            results[name] = df
    finally:
        conn.close()
    return results


if __name__ == "__main__":
    for query_name, result in run_analysis().items():
        print(f"\n=== {query_name} ===")
        print(result.head(10).to_string(index=False))