from datetime import date, timedelta

import pandas as pd
import requests

from src.utils import RAW_DIR, get_logger

logger = get_logger(__name__)

CSV_FILES = {
    "customers": "olist_customers_dataset.csv",
    "geolocation": "olist_geolocation_dataset.csv",
    "order_items": "olist_order_items_dataset.csv",
    "order_payments": "olist_order_payments_dataset.csv",
    "order_reviews": "olist_order_reviews_dataset.csv",
    "orders": "olist_orders_dataset.csv",
    "products": "olist_products_dataset.csv",
    "sellers": "olist_sellers_dataset.csv",
    "category_translation": "product_category_name_translation.csv",
}


def extract_csv_tables() -> dict:
    """Read all raw Olist CSV files into DataFrames."""
    tables = {}
    for name, filename in CSV_FILES.items():
        path = RAW_DIR / filename
        if not path.exists():
            raise FileNotFoundError(f"Missing raw file: {path}")
        df = pd.read_csv(path)
        logger.info("Extracted %-22s rows=%-8d cols=%d", name, len(df), df.shape[1])
        tables[name] = df
    return tables


def extract_exchange_rates(start="2016-09-01", end="2018-10-31",
                           base="BRL", symbols="USD,INR") -> pd.DataFrame:
    """Fetch daily exchange rates from the Frankfurter API in chunks."""
    rows = []
    current = date.fromisoformat(start)
    end_date = date.fromisoformat(end)
    while current <= end_date:
        chunk_end = min(current + timedelta(days=80), end_date)
        url = f"https://api.frankfurter.dev/v1/{current}..{chunk_end}"
        resp = requests.get(url, params={"base": base, "symbols": symbols}, timeout=30)
        resp.raise_for_status()
        for day, rates in resp.json()["rates"].items():
            row = {"rate_date": day}
            for cur_code, value in rates.items():
                row[f"{base}_to_{cur_code}"] = value
            rows.append(row)
        current = chunk_end + timedelta(days=1)

    df = pd.DataFrame(rows).drop_duplicates("rate_date").sort_values("rate_date")
    logger.info("Extracted exchange_rates rows=%d from API", len(df))
    return df