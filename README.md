\# E-commerce ETL Pipeline with Data Quality Checks



An end-to-end ETL pipeline built with Python, Pandas and SQL. It loads the Olist Brazilian e-commerce dataset (9 CSV tables, about 1.5M rows) and a currency-rates REST API into a SQLite star schema, validates the warehouse with 54 automated data-quality checks, and runs analytical SQL using CTEs, window functions and subqueries.



\## Architecture



```mermaid

flowchart LR

&#x20;   A\[9 Olist CSV files] --> C\[Extract]

&#x20;   B\[Frankfurter FX API] --> C

&#x20;   C --> D\[Transform]

&#x20;   D --> E\[Load to SQLite star schema]

&#x20;   E --> F\[54 data quality checks]

&#x20;   F -->|all errors clear| G\[Analytical SQL]

&#x20;   F -->|error found| H\[Stop pipeline]

```



\## Data model



```mermaid

erDiagram

&#x20;   dim_customers ||--o{ fact\_orders : places

&#x20;   dim_date ||--o{ fact\_orders : "purchased on"

&#x20;   fact_orders ||--o{ fact\_order\_items : contains

&#x20;   dim_products ||--o{ fact\_order\_items : "sold as"

&#x20;   dim_sellers ||--o{ fact\_order\_items : "sold by"

&#x20;   dim_customers ||--o{ fact\_order\_items : "bought by"

&#x20;   dim_date ||--o{ fact\_order\_items : "purchased on"

```



\## Pipeline stages



| Stage | Files | What it does |

|---|---|---|

| Extract | `src/extract.py` | Reads 9 CSVs. Pulls daily BRL to USD/INR rates from the Frankfurter API with retries (exponential backoff) and a cached fallback if the API is down. |

| Transform | `src/transform.py` | Removes duplicates, fixes types, derives delivery metrics, keeps the latest review per order, aggregates payments per order, and converts prices to USD and INR using the latest available rate on or before each purchase date. |

| Load | `src/load.py`, `sql/schema.sql` | Creates tables with primary keys, foreign keys and indexes, bulk loads, and reconciles row counts against the source DataFrames. |

| Quality | `src/quality.py` | 54 checks: schema, completeness, nulls, duplicates, referential integrity and business rules. Errors stop the pipeline, warnings are logged. Report saved to `docs/data\_quality\_report.csv`. |

| Analysis | `src/analysis.py`, `sql/analysis\_queries.sql` | Six business queries. Results saved to `docs/analysis/`. |

| Optimize | `src/optimize.py` | Compares `EXPLAIN QUERY PLAN` and runtime before and after adding an index. |



\## Results (measured on my laptop)



\- Full pipeline: 16 to 41 seconds end to end (manual run vs. scheduled run on battery).

\- Data quality: 50 checks passed, 4 warnings, 0 failures. The warnings were 775 orders with no items, 8 delivered orders with no delivery date, 1 order with no payment record, and 249 orders whose payment total differs from the item total by more than 1 BRL. The status breakdown of the 775 is in `docs/analysis/orders\_without\_items\_by\_status.csv`.

\- Query optimization: an index on `fact\_order\_items(order\_status)` cut a filtered query from 30.2 ms to 0.21 ms (about 142x). The plan changed from `SCAN` to `SEARCH ... USING INDEX`.

\- Example insight: among states, Alagoas (AL) had the highest late-delivery rate at 21.4%, with an average delivery time of 24.0 days.

\- Tests: 8 pytest unit tests cover the transform logic.



\## Design decisions



\- \*\*Errors vs warnings:\*\* structural problems (missing keys, orphan foreign keys, invalid values) stop the run. Known data quirks (for example orders that never shipped) are logged as warnings, so they are tracked without blocking the pipeline.

\- \*\*As-of join for exchange rates:\*\* the API has no rates for weekends or holidays, so each order uses the most recent earlier rate.

\- \*\*Idempotent load:\*\* tables are dropped and recreated on every run, so re-running never creates duplicates.

\- \*\*Raw data is not committed:\*\* see below for how to download it.



\## How to run (Windows)



1\. Download the dataset from https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce and place all 9 CSV files in `data/raw/`.

2\. Set up the environment:

```bat

python -m venv venv

venv\\Scripts\\activate

pip install -r requirements.txt

```

3\. Run the full pipeline:

```bat

python main.py

```

4\. Run the tests:

```bat

python -m pytest -v

```

5\. Run the index optimization demo:

```bat

python -m src.optimize

```

The warehouse is created at `data/processed/olist\_warehouse.db` and logs are written to `logs/pipeline.log`. `run\_pipeline.bat` can be scheduled with Windows Task Scheduler.



\## Tech stack



Python, Pandas, SQL (SQLite), requests, pytest, Git, Windows Task Scheduler.



\## Data sources



Olist Brazilian E-commerce dataset (Kaggle) and the Frankfurter exchange-rate API.

