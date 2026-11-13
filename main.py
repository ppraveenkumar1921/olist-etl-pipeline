from src.extract import extract_csv_tables, extract_exchange_rates
from src.load import load_all
from src.transform import transform_all
from src.utils import RAW_DIR

if __name__ == "__main__":
    tables = extract_csv_tables()
    rates = extract_exchange_rates()
    rates.to_csv(RAW_DIR / "exchange_rates.csv", index=False)

    clean = transform_all(tables, rates)
    load_all(clean)