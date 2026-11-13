-- Star schema for the Olist warehouse (SQLite)
PRAGMA foreign_keys = OFF;

DROP TABLE IF EXISTS fact_order_items;
DROP TABLE IF EXISTS fact_orders;
DROP TABLE IF EXISTS dim_date;
DROP TABLE IF EXISTS dim_products;
DROP TABLE IF EXISTS dim_sellers;
DROP TABLE IF EXISTS dim_customers;

CREATE TABLE dim_customers (
    customer_id              TEXT PRIMARY KEY,
    customer_unique_id       TEXT NOT NULL,
    customer_zip_code_prefix INTEGER,
    customer_city            TEXT,
    customer_state           TEXT
);

CREATE TABLE dim_sellers (
    seller_id              TEXT PRIMARY KEY,
    seller_zip_code_prefix INTEGER,
    seller_city            TEXT,
    seller_state           TEXT
);

CREATE TABLE dim_products (
    product_id                    TEXT PRIMARY KEY,
    product_category_name         TEXT,
    product_name_length           REAL,
    product_description_length    REAL,
    product_photos_qty            REAL,
    product_weight_g              REAL,
    product_length_cm             REAL,
    product_height_cm             REAL,
    product_width_cm              REAL,
    product_category_name_english TEXT
);

CREATE TABLE dim_date (
    date_key    INTEGER PRIMARY KEY,
    full_date   TEXT NOT NULL,
    year        INTEGER,
    quarter     INTEGER,
    month       INTEGER,
    month_name  TEXT,
    day_of_week TEXT,
    is_weekend  INTEGER
);

CREATE TABLE fact_orders (
    order_id                      TEXT PRIMARY KEY,
    customer_id                   TEXT NOT NULL,
    order_status                  TEXT,
    order_purchase_timestamp      TEXT,
    order_approved_at             TEXT,
    order_delivered_carrier_date  TEXT,
    order_delivered_customer_date TEXT,
    order_estimated_delivery_date TEXT,
    delivery_days                 INTEGER,
    delivery_delay_days           INTEGER,
    is_late                       INTEGER,
    total_payment_value           REAL,
    max_installments              INTEGER,
    payment_types                 TEXT,
    review_score                  REAL,
    date_key                      INTEGER NOT NULL,
    FOREIGN KEY (customer_id) REFERENCES dim_customers (customer_id),
    FOREIGN KEY (date_key)    REFERENCES dim_date (date_key)
);

CREATE TABLE fact_order_items (
    order_id             TEXT NOT NULL,
    order_item_id        INTEGER NOT NULL,
    product_id           TEXT NOT NULL,
    seller_id            TEXT NOT NULL,
    customer_id          TEXT NOT NULL,
    date_key             INTEGER NOT NULL,
    order_status         TEXT,
    shipping_limit_date  TEXT,
    price                REAL,
    freight_value        REAL,
    total_item_value_brl REAL,
    price_usd            REAL,
    price_inr            REAL,
    PRIMARY KEY (order_id, order_item_id),
    FOREIGN KEY (order_id)    REFERENCES fact_orders (order_id),
    FOREIGN KEY (product_id)  REFERENCES dim_products (product_id),
    FOREIGN KEY (seller_id)   REFERENCES dim_sellers (seller_id),
    FOREIGN KEY (customer_id) REFERENCES dim_customers (customer_id),
    FOREIGN KEY (date_key)    REFERENCES dim_date (date_key)
);

CREATE INDEX idx_orders_customer  ON fact_orders (customer_id);
CREATE INDEX idx_orders_date      ON fact_orders (date_key);
CREATE INDEX idx_orders_status    ON fact_orders (order_status);
CREATE INDEX idx_items_product    ON fact_order_items (product_id);
CREATE INDEX idx_items_seller     ON fact_order_items (seller_id);
CREATE INDEX idx_items_date       ON fact_order_items (date_key);