import numpy as np
import pandas as pd

from src.utils import get_logger

logger = get_logger(__name__)

ORDER_DATE_COLS = [
    "order_purchase_timestamp",
    "order_approved_at",
    "order_delivered_carrier_date",
    "order_delivered_customer_date",
    "order_estimated_delivery_date",
]


def clean_orders(orders: pd.DataFrame) -> pd.DataFrame:
    df = orders.drop_duplicates("order_id").copy()
    for col in ORDER_DATE_COLS:
        df[col] = pd.to_datetime(df[col], errors="coerce")

    df["delivery_days"] = (
        df["order_delivered_customer_date"] - df["order_purchase_timestamp"]
    ).dt.days
    df["delivery_delay_days"] = (
        df["order_delivered_customer_date"] - df["order_estimated_delivery_date"]
    ).dt.days
    delay = df["delivery_delay_days"]
    df["is_late"] = (delay > 0).astype("Int64").where(delay.notna())
    return df


def clean_reviews(reviews: pd.DataFrame) -> pd.DataFrame:
    """Keep only the latest review per order."""
    df = reviews.copy()
    df["review_answer_timestamp"] = pd.to_datetime(
        df["review_answer_timestamp"], errors="coerce"
    )
    df = df.sort_values("review_answer_timestamp").drop_duplicates(
        "order_id", keep="last"
    )
    return df[["order_id", "review_score"]]


def aggregate_payments(payments: pd.DataFrame) -> pd.DataFrame:
    """Collapse multiple payment rows into one row per order."""
    return (
        payments.groupby("order_id")
        .agg(
            total_payment_value=("payment_value", "sum"),
            max_installments=("payment_installments", "max"),
            payment_types=("payment_type", lambda s: ",".join(sorted(set(s)))),
        )
        .reset_index()
    )


def build_dim_customers(customers: pd.DataFrame) -> pd.DataFrame:
    df = customers.drop_duplicates("customer_id").copy()
    df["customer_city"] = df["customer_city"].str.strip().str.title()
    df["customer_state"] = df["customer_state"].str.strip().str.upper()
    return df


def build_dim_sellers(sellers: pd.DataFrame) -> pd.DataFrame:
    df = sellers.drop_duplicates("seller_id").copy()
    df["seller_city"] = df["seller_city"].str.strip().str.title()
    df["seller_state"] = df["seller_state"].str.strip().str.upper()
    return df


def build_dim_products(products: pd.DataFrame, translation: pd.DataFrame) -> pd.DataFrame:
    df = products.drop_duplicates("product_id").copy()
    # fix the misspelled column names in the source data
    df = df.rename(
        columns={
            "product_name_lenght": "product_name_length",
            "product_description_lenght": "product_description_length",
        }
    )
    df = df.merge(translation, on="product_category_name", how="left")
    # categories without a translation fall back to the Portuguese name
    df["product_category_name_english"] = df["product_category_name_english"].fillna(
        df["product_category_name"]
    )
    df["product_category_name"] = df["product_category_name"].fillna("unknown")
    df["product_category_name_english"] = df["product_category_name_english"].fillna(
        "unknown"
    )
    return df


def build_dim_date(orders: pd.DataFrame) -> pd.DataFrame:
    start = orders["order_purchase_timestamp"].min().normalize()
    end = orders["order_purchase_timestamp"].max().normalize()
    df = pd.DataFrame({"full_date": pd.date_range(start, end, freq="D")})
    df["date_key"] = df["full_date"].dt.strftime("%Y%m%d").astype(int)
    df["year"] = df["full_date"].dt.year
    df["quarter"] = df["full_date"].dt.quarter
    df["month"] = df["full_date"].dt.month
    df["month_name"] = df["full_date"].dt.month_name()
    df["day_of_week"] = df["full_date"].dt.day_name()
    df["is_weekend"] = df["full_date"].dt.dayofweek.isin([5, 6]).astype(int)
    return df


def attach_exchange_rates(df: pd.DataFrame, rates: pd.DataFrame) -> pd.DataFrame:
    """Match each row to the latest rate on or before its purchase date.
    This handles weekends and holidays, which have no rate."""
    rates = rates.copy()
    rates["rate_date"] = pd.to_datetime(rates["rate_date"]).astype("datetime64[ns]")
    rates = rates.sort_values("rate_date")

    left = df.copy()
    left["purchase_date"] = left["purchase_date"].astype("datetime64[ns]")
    left = left.sort_values("purchase_date")
    return pd.merge_asof(
        left,
        rates,
        left_on="purchase_date",
        right_on="rate_date",
        direction="backward",
    )


def build_fact_order_items(order_items, orders, rates) -> pd.DataFrame:
    items = order_items.drop_duplicates(["order_id", "order_item_id"]).copy()
    items["shipping_limit_date"] = pd.to_datetime(
        items["shipping_limit_date"], errors="coerce"
    )

    order_cols = orders[["order_id", "customer_id", "order_status", "order_purchase_timestamp"]]
    df = items.merge(order_cols, on="order_id", how="inner")
    df["purchase_date"] = df["order_purchase_timestamp"].dt.normalize()
    df = attach_exchange_rates(df, rates)

    df["total_item_value_brl"] = (df["price"] + df["freight_value"]).round(2)
    df["price_usd"] = (df["price"] * df["BRL_to_USD"]).round(2)
    df["price_inr"] = (df["price"] * df["BRL_to_INR"]).round(2)
    df["date_key"] = df["purchase_date"].dt.strftime("%Y%m%d").astype(int)

    cols = [
        "order_id", "order_item_id", "product_id", "seller_id", "customer_id",
        "date_key", "order_status", "shipping_limit_date", "price",
        "freight_value", "total_item_value_brl", "price_usd", "price_inr",
    ]
    return df[cols].sort_values(["order_id", "order_item_id"]).reset_index(drop=True)


def build_fact_orders(orders, payments, reviews) -> pd.DataFrame:
    df = orders.merge(aggregate_payments(payments), on="order_id", how="left")
    df = df.merge(clean_reviews(reviews), on="order_id", how="left")
    df["date_key"] = df["order_purchase_timestamp"].dt.strftime("%Y%m%d").astype(int)
    return df


def transform_all(tables: dict, rates: pd.DataFrame) -> dict:
    orders = clean_orders(tables["orders"])

    result = {
        "dim_customers": build_dim_customers(tables["customers"]),
        "dim_sellers": build_dim_sellers(tables["sellers"]),
        "dim_products": build_dim_products(
            tables["products"], tables["category_translation"]
        ),
        "dim_date": build_dim_date(orders),
        "fact_orders": build_fact_orders(
            orders, tables["order_payments"], tables["order_reviews"]
        ),
        "fact_order_items": build_fact_order_items(
            tables["order_items"], orders, rates
        ),
    }
    for name, df in result.items():
        logger.info("Transformed %-18s rows=%-8d cols=%d", name, len(df), df.shape[1])
    return result