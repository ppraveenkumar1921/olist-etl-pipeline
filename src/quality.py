import sqlite3

import pandas as pd

from src.load import DB_PATH
from src.utils import BASE_DIR, get_logger

logger = get_logger(__name__)

REPORT_PATH = BASE_DIR / "docs" / "data_quality_report.csv"


class DataQualityError(Exception):
    """Raised when one or more error-severity checks fail."""


EXPECTED_COLUMNS = {
    "dim_customers": {
        "customer_id", "customer_unique_id", "customer_zip_code_prefix",
        "customer_city", "customer_state",
    },
    "dim_sellers": {
        "seller_id", "seller_zip_code_prefix", "seller_city", "seller_state",
    },
    "dim_products": {
        "product_id", "product_category_name", "product_name_length",
        "product_description_length", "product_photos_qty", "product_weight_g",
        "product_length_cm", "product_height_cm", "product_width_cm",
        "product_category_name_english",
    },
    "dim_date": {
        "date_key", "full_date", "year", "quarter", "month", "month_name",
        "day_of_week", "is_weekend",
    },
    "fact_orders": {
        "order_id", "customer_id", "order_status", "order_purchase_timestamp",
        "order_approved_at", "order_delivered_carrier_date",
        "order_delivered_customer_date", "order_estimated_delivery_date",
        "delivery_days", "delivery_delay_days", "is_late", "total_payment_value",
        "max_installments", "payment_types", "review_score", "date_key",
    },
    "fact_order_items": {
        "order_id", "order_item_id", "product_id", "seller_id", "customer_id",
        "date_key", "order_status", "shipping_limit_date", "price",
        "freight_value", "total_item_value_brl", "price_usd", "price_inr",
    },
}

NOT_NULL = {
    "dim_customers": ["customer_id", "customer_unique_id"],
    "dim_sellers": ["seller_id"],
    "dim_products": ["product_id"],
    "dim_date": ["date_key", "full_date"],
    "fact_orders": [
        "order_id", "customer_id", "order_status",
        "order_purchase_timestamp", "date_key",
    ],
    "fact_order_items": [
        "order_id", "order_item_id", "product_id", "seller_id",
        "customer_id", "date_key", "price",
    ],
}

UNIQUE_KEYS = {
    "dim_customers": ["customer_id"],
    "dim_sellers": ["seller_id"],
    "dim_products": ["product_id"],
    "dim_date": ["date_key"],
    "fact_orders": ["order_id"],
    "fact_order_items": ["order_id", "order_item_id"],
}

# (child table, child column, parent table, parent column)
FOREIGN_KEYS = [
    ("fact_orders", "customer_id", "dim_customers", "customer_id"),
    ("fact_orders", "date_key", "dim_date", "date_key"),
    ("fact_order_items", "order_id", "fact_orders", "order_id"),
    ("fact_order_items", "product_id", "dim_products", "product_id"),
    ("fact_order_items", "seller_id", "dim_sellers", "seller_id"),
    ("fact_order_items", "customer_id", "dim_customers", "customer_id"),
    ("fact_order_items", "date_key", "dim_date", "date_key"),
]

VALID_STATUSES = (
    "delivered", "shipped", "canceled", "unavailable",
    "invoiced", "processing", "created", "approved",
)

# (table, description, SQL returning the number of bad rows, severity)
BUSINESS_RULES = [
    (
        "fact_orders",
        "order_status is one of the 8 valid values",
        "SELECT COUNT(*) FROM fact_orders WHERE order_status NOT IN ("
        + ",".join(f"'{s}'" for s in VALID_STATUSES) + ")",
        "error",
    ),
    (
        "fact_order_items",
        "price is greater than 0",
        "SELECT COUNT(*) FROM fact_order_items WHERE price <= 0",
        "error",
    ),
    (
        "fact_order_items",
        "freight_value is not negative",
        "SELECT COUNT(*) FROM fact_order_items WHERE freight_value < 0",
        "error",
    ),
    (
        "fact_orders",
        "review_score is between 1 and 5",
        "SELECT COUNT(*) FROM fact_orders "
        "WHERE review_score IS NOT NULL AND review_score NOT BETWEEN 1 AND 5",
        "error",
    ),
    (
        "fact_order_items",
        "price_usd was converted for every item",
        "SELECT COUNT(*) FROM fact_order_items WHERE price_usd IS NULL",
        "error",
    ),
    (
        "fact_order_items",
        "price_inr was converted for every item",
        "SELECT COUNT(*) FROM fact_order_items WHERE price_inr IS NULL",
        "error",
    ),
    (
        "fact_orders",
        "delivery_days is not negative",
        "SELECT COUNT(*) FROM fact_orders WHERE delivery_days < 0",
        "warn",
    ),
    (
        "fact_orders",
        "delivered orders have a customer delivery date",
        "SELECT COUNT(*) FROM fact_orders WHERE order_status = 'delivered' "
        "AND order_delivered_customer_date IS NULL",
        "warn",
    ),
    (
        "fact_orders",
        "every order has at least one item",
        "SELECT COUNT(*) FROM fact_orders o "
        "LEFT JOIN fact_order_items i ON o.order_id = i.order_id "
        "WHERE i.order_id IS NULL",
        "warn",
    ),
    (
        "fact_orders",
        "every order has a payment record",
        "SELECT COUNT(*) FROM fact_orders WHERE total_payment_value IS NULL",
        "warn",
    ),
    (
        "fact_orders",
        "payment total matches item total (within 1.00 BRL)",
        "SELECT COUNT(*) FROM fact_orders o JOIN ("
        "SELECT order_id, SUM(total_item_value_brl) AS items_total "
        "FROM fact_order_items GROUP BY order_id) i ON o.order_id = i.order_id "
        "WHERE o.total_payment_value IS NOT NULL "
        "AND ABS(o.total_payment_value - i.items_total) > 1.0",
        "warn",
    ),
]


def _record(results, category, table, check, bad_rows, severity):
    status = "PASS" if bad_rows == 0 else ("FAIL" if severity == "error" else "WARN")
    results.append(
        {
            "category": category,
            "table": table,
            "check": check,
            "severity": severity,
            "bad_rows": bad_rows,
            "status": status,
        }
    )
    log = logger.info if status == "PASS" else (
        logger.error if status == "FAIL" else logger.warning
    )
    log("%-4s | %-11s | %-17s | %s (bad_rows=%d)",
        status, category, table, check, bad_rows)


def _count(conn, sql):
    return conn.execute(sql).fetchone()[0]


def check_schema(conn, results):
    for table, expected in EXPECTED_COLUMNS.items():
        actual = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
        diff = len(expected.symmetric_difference(actual))
        _record(results, "schema", table, "columns match expected schema", diff, "error")


def check_row_counts(conn, results):
    for table in EXPECTED_COLUMNS:
        n = _count(conn, f"SELECT COUNT(*) FROM {table}")
        _record(results, "completeness", table, f"table is not empty (rows={n})",
                0 if n > 0 else 1, "error")


def check_nulls(conn, results):
    for table, cols in NOT_NULL.items():
        for col in cols:
            bad = _count(conn, f"SELECT COUNT(*) FROM {table} WHERE {col} IS NULL")
            _record(results, "nulls", table, f"{col} has no nulls", bad, "error")


def check_duplicates(conn, results):
    for table, keys in UNIQUE_KEYS.items():
        key_list = ", ".join(keys)
        bad = _count(
            conn,
            f"SELECT COUNT(*) FROM (SELECT 1 FROM {table} "
            f"GROUP BY {key_list} HAVING COUNT(*) > 1)",
        )
        _record(results, "duplicates", table, f"({key_list}) is unique", bad, "error")


def check_referential_integrity(conn, results):
    for child, ccol, parent, pcol in FOREIGN_KEYS:
        bad = _count(
            conn,
            f"SELECT COUNT(*) FROM {child} c LEFT JOIN {parent} p "
            f"ON c.{ccol} = p.{pcol} WHERE p.{pcol} IS NULL",
        )
        _record(results, "integrity", child,
                f"{ccol} exists in {parent}.{pcol}", bad, "error")


def check_business_rules(conn, results):
    for table, description, sql, severity in BUSINESS_RULES:
        _record(results, "business", table, description, _count(conn, sql), severity)


def run_quality_checks(fail_on_error: bool = True) -> pd.DataFrame:
    conn = sqlite3.connect(DB_PATH)
    results = []
    try:
        check_schema(conn, results)
        if all(r["status"] == "PASS" for r in results):
            check_row_counts(conn, results)
            check_nulls(conn, results)
            check_duplicates(conn, results)
            check_referential_integrity(conn, results)
            check_business_rules(conn, results)
        else:
            logger.error("Schema mismatch found, skipping the remaining checks")
    finally:
        conn.close()

    report = pd.DataFrame(results)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    report.to_csv(REPORT_PATH, index=False)

    counts = report["status"].value_counts()
    passed, warned, failed = (int(counts.get(s, 0)) for s in ("PASS", "WARN", "FAIL"))
    logger.info(
        "Data quality summary: total=%d passed=%d warnings=%d failed=%d",
        len(report), passed, warned, failed,
    )

    if failed and fail_on_error:
        raise DataQualityError(
            f"{failed} data quality check(s) failed, see {REPORT_PATH}"
        )
    return report


if __name__ == "__main__":
    run_quality_checks()