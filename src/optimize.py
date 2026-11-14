import sqlite3
import time

from src.load import DB_PATH
from src.utils import get_logger

logger = get_logger(__name__)

INDEX_NAME = "idx_items_status"
TEST_QUERY = """
SELECT COUNT(*) AS items, ROUND(SUM(price), 2) AS revenue_brl
FROM fact_order_items
WHERE order_status = 'canceled'
"""


def explain(conn, sql):
    rows = conn.execute("EXPLAIN QUERY PLAN " + sql).fetchall()
    return [row[3] for row in rows]


def time_query(conn, sql, runs=20):
    """Average execution time in milliseconds."""
    conn.execute(sql).fetchall()  # warm-up run
    start = time.perf_counter()
    for _ in range(runs):
        conn.execute(sql).fetchall()
    return (time.perf_counter() - start) / runs * 1000


def run_optimization_demo():
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(f"DROP INDEX IF EXISTS {INDEX_NAME}")
        conn.commit()
        before_plan = explain(conn, TEST_QUERY)
        before_ms = time_query(conn, TEST_QUERY)

        conn.execute(f"CREATE INDEX {INDEX_NAME} ON fact_order_items (order_status)")
        conn.execute("ANALYZE")
        conn.commit()
        after_plan = explain(conn, TEST_QUERY)
        after_ms = time_query(conn, TEST_QUERY)

        result = conn.execute(TEST_QUERY).fetchone()
    finally:
        conn.close()

    speedup = before_ms / after_ms if after_ms else float("inf")
    logger.info("Query result: items=%s revenue_brl=%s", result[0], result[1])
    logger.info("BEFORE index: %s | %.2f ms", before_plan, before_ms)
    logger.info("AFTER  index: %s | %.2f ms", after_plan, after_ms)
    logger.info("Speedup: %.1fx", speedup)


if __name__ == "__main__":
    run_optimization_demo()