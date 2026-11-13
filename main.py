from src.extract import extract_csv_tables, extract_exchange_rates
from src.utils import RAW_DIR

if __name__ == "__main__":
    tables = extract_csv_tables()
    rates = extract_exchange_rates()
    rates.to_csv(RAW_DIR / "exchange_rates.csv", index=False)
    print(rates.head())