import sqlite3

import pandas as pd

from src.utils import BASE_DIR, PROCESSED_DIR, get_logger

logger = get_logger(__name__)

DB_PATH = PROCESSED_DIR / "olist_warehouse.db"
SCHEMA_PATH = BASE_DIR / "sql" / "schema.sql"

# dimensions first, then facts
LOAD_ORDER = [
    "dim_customers",
    "dim_sellers",
    "dim_products",
    "dim_date",
    "fact_orders",
    "fact_order_items",
]


def _prepare(df: pd.DataFrame) -> pd.DataFrame:
    """Convert dates to text and nullable ints to floats so SQLite accepts them."""
    df = df.copy()
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            fmt = "%Y-%m-%d" if col == "full_date" else "%Y-%m-%d %H:%M:%S"
            df[col] = df[col].dt.strftime(fmt)
        elif str(df[col].dtype) == "Int64":
            df[col] = df[col].astype("float64")
    return df


def load_all(tables: dict) -> dict:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        logger.info("Schema created at %s", DB_PATH)

        for name in LOAD_ORDER:
            _prepare(tables[name]).to_sql(
                name, conn, if_exists="append", index=False, chunksize=10000
            )
            logger.info("Loaded %-18s rows=%d", name, len(tables[name]))
        conn.commit()

        # reconciliation: DataFrame rows must equal database rows
        counts = {}
        for name in LOAD_ORDER:
            counts[name] = conn.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
            if counts[name] != len(tables[name]):
                raise ValueError(
                    f"Row count mismatch in {name}: "
                    f"expected {len(tables[name])}, found {counts[name]}"
                )
        logger.info("Load reconciliation passed for all %d tables", len(counts))
        return counts
    finally:
        conn.close()