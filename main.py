from src.extract import extract_csv_tables, extract_exchange_rates
from src.transform import transform_all
from src.utils import PROCESSED_DIR, RAW_DIR

if __name__ == "__main__":
    tables = extract_csv_tables()
    rates = extract_exchange_rates()
    rates.to_csv(RAW_DIR / "exchange_rates.csv", index=False)

    clean = transform_all(tables, rates)

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    for name, df in clean.items():
        df.to_csv(PROCESSED_DIR / f"{name}.csv", index=False)

    print(clean["fact_order_items"].head())
    print(clean["fact_orders"][["order_id", "delivery_days", "is_late", "total_payment_value", "review_score"]].head())