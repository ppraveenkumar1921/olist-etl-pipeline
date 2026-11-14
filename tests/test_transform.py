import pandas as pd

from src.transform import (
    aggregate_payments,
    attach_exchange_rates,
    build_dim_customers,
    build_dim_date,
    build_dim_products,
    build_fact_order_items,
    clean_orders,
    clean_reviews,
)


def make_orders():
    return pd.DataFrame(
        {
            "order_id": ["o1", "o1", "o2"],
            "customer_id": ["c1", "c1", "c2"],
            "order_status": ["delivered", "delivered", "canceled"],
            "order_purchase_timestamp": [
                "2018-01-01 10:00:00", "2018-01-01 10:00:00", "2018-01-02 09:00:00",
            ],
            "order_approved_at": [
                "2018-01-01 11:00:00", "2018-01-01 11:00:00", "2018-01-02 10:00:00",
            ],
            "order_delivered_carrier_date": [
                "2018-01-03 10:00:00", "2018-01-03 10:00:00", None,
            ],
            "order_delivered_customer_date": [
                "2018-01-11 10:00:00", "2018-01-11 10:00:00", None,
            ],
            "order_estimated_delivery_date": [
                "2018-01-09 00:00:00", "2018-01-09 00:00:00", "2018-01-20 00:00:00",
            ],
        }
    )


def test_clean_orders_removes_duplicates_and_computes_delivery_metrics():
    result = clean_orders(make_orders()).set_index("order_id")
    assert len(result) == 2
    assert result.loc["o1", "delivery_days"] == 10
    assert result.loc["o1", "delivery_delay_days"] == 2
    assert result.loc["o1", "is_late"] == 1
    assert pd.isna(result.loc["o2", "delivery_days"])
    assert pd.isna(result.loc["o2", "is_late"])


def test_clean_reviews_keeps_latest_review_per_order():
    reviews = pd.DataFrame(
        {
            "order_id": ["o1", "o1", "o2"],
            "review_score": [1, 5, 3],
            "review_answer_timestamp": [
                "2018-01-01 10:00:00", "2018-01-05 10:00:00", "2018-01-02 10:00:00",
            ],
        }
    )
    result = clean_reviews(reviews).set_index("order_id")
    assert len(result) == 2
    assert result.loc["o1", "review_score"] == 5


def test_aggregate_payments_returns_one_row_per_order():
    payments = pd.DataFrame(
        {
            "order_id": ["o1", "o1", "o2"],
            "payment_value": [60.0, 40.0, 25.5],
            "payment_installments": [1, 3, 2],
            "payment_type": ["credit_card", "voucher", "boleto"],
        }
    )
    result = aggregate_payments(payments).set_index("order_id")
    assert len(result) == 2
    assert result.loc["o1", "total_payment_value"] == 100.0
    assert result.loc["o1", "max_installments"] == 3
    assert result.loc["o1", "payment_types"] == "credit_card,voucher"


def test_dim_customers_standardizes_text_and_removes_duplicates():
    customers = pd.DataFrame(
        {
            "customer_id": ["c1", "c1"],
            "customer_unique_id": ["u1", "u1"],
            "customer_zip_code_prefix": [1000, 1000],
            "customer_city": ["  sao paulo ", "  sao paulo "],
            "customer_state": [" sp", " sp"],
        }
    )
    result = build_dim_customers(customers)
    assert len(result) == 1
    assert result.iloc[0]["customer_city"] == "Sao Paulo"
    assert result.iloc[0]["customer_state"] == "SP"


def test_dim_products_renames_columns_and_handles_missing_categories():
    products = pd.DataFrame(
        {
            "product_id": ["p1", "p2", "p3"],
            "product_category_name": ["beleza_saude", "categoria_nova", None],
            "product_name_lenght": [40, 50, 60],
            "product_description_lenght": [100, 200, 300],
            "product_photos_qty": [1, 2, 3],
            "product_weight_g": [500, 600, 700],
            "product_length_cm": [10, 20, 30],
            "product_height_cm": [5, 6, 7],
            "product_width_cm": [8, 9, 10],
        }
    )
    translation = pd.DataFrame(
        {
            "product_category_name": ["beleza_saude"],
            "product_category_name_english": ["health_beauty"],
        }
    )
    result = build_dim_products(products, translation).set_index("product_id")
    assert "product_name_length" in result.columns
    assert "product_name_lenght" not in result.columns
    assert result.loc["p1", "product_category_name_english"] == "health_beauty"
    assert result.loc["p2", "product_category_name_english"] == "categoria_nova"
    assert result.loc["p3", "product_category_name"] == "unknown"
    assert result.loc["p3", "product_category_name_english"] == "unknown"


def test_dim_date_covers_full_range_and_flags_weekends():
    orders = pd.DataFrame(
        {
            "order_purchase_timestamp": pd.to_datetime(
                ["2018-01-05 14:00:00", "2018-01-08 09:00:00"]
            )
        }
    )
    result = build_dim_date(orders)
    assert list(result["date_key"]) == [20180105, 20180106, 20180107, 20180108]
    weekend = result.set_index("date_key")["is_weekend"]
    assert weekend[20180105] == 0  # Friday
    assert weekend[20180106] == 1  # Saturday


def test_exchange_rate_uses_latest_prior_rate_for_weekends():
    df = pd.DataFrame(
        {
            "order_id": ["o1", "o2"],
            "purchase_date": pd.to_datetime(["2018-01-06", "2018-01-08"]),
        }
    )
    rates = pd.DataFrame(
        {
            "rate_date": ["2018-01-05", "2018-01-08"],
            "BRL_to_USD": [0.30, 0.31],
            "BRL_to_INR": [19.0, 20.0],
        }
    )
    result = attach_exchange_rates(df, rates).set_index("order_id")
    assert result.loc["o1", "BRL_to_USD"] == 0.30  # Saturday uses Friday's rate
    assert result.loc["o2", "BRL_to_USD"] == 0.31


def test_fact_order_items_converts_price_to_usd_and_inr():
    order_items = pd.DataFrame(
        {
            "order_id": ["o1"],
            "order_item_id": [1],
            "product_id": ["p1"],
            "seller_id": ["s1"],
            "shipping_limit_date": ["2018-01-08 10:00:00"],
            "price": [100.0],
            "freight_value": [20.0],
        }
    )
    orders = pd.DataFrame(
        {
            "order_id": ["o1"],
            "customer_id": ["c1"],
            "order_status": ["delivered"],
            "order_purchase_timestamp": pd.to_datetime(["2018-01-06 10:00:00"]),
        }
    )
    rates = pd.DataFrame(
        {"rate_date": ["2018-01-05"], "BRL_to_USD": [0.30], "BRL_to_INR": [19.0]}
    )
    row = build_fact_order_items(order_items, orders, rates).iloc[0]
    assert row["total_item_value_brl"] == 120.0
    assert row["price_usd"] == 30.0
    assert row["price_inr"] == 1900.0
    assert row["date_key"] == 20180106