-- name: orders_without_items_by_status
SELECT o.order_status,
       COUNT(*) AS orders_without_items
FROM fact_orders o
LEFT JOIN fact_order_items i ON o.order_id = i.order_id
WHERE i.order_id IS NULL
GROUP BY o.order_status
ORDER BY orders_without_items DESC;

-- name: monthly_revenue_growth
WITH monthly AS (
    SELECT d.year,
           d.month,
           printf('%04d-%02d', d.year, d.month) AS year_month,
           COUNT(DISTINCT i.order_id)           AS orders,
           ROUND(SUM(i.price), 2)               AS revenue_brl
    FROM fact_order_items i
    JOIN dim_date d ON i.date_key = d.date_key
    WHERE i.order_status = 'delivered'
    GROUP BY d.year, d.month
)
SELECT year_month,
       orders,
       revenue_brl,
       LAG(revenue_brl) OVER (ORDER BY year_month) AS prev_month_revenue,
       ROUND(100.0 * (revenue_brl - LAG(revenue_brl) OVER (ORDER BY year_month))
             / LAG(revenue_brl) OVER (ORDER BY year_month), 1) AS mom_growth_pct,
       ROUND(SUM(revenue_brl) OVER (ORDER BY year_month), 2)   AS cumulative_revenue_brl
FROM monthly
ORDER BY year_month;

-- name: top_3_sellers_per_state
WITH seller_revenue AS (
    SELECT s.seller_state,
           s.seller_id,
           COUNT(DISTINCT i.order_id) AS orders,
           ROUND(SUM(i.price), 2)     AS revenue_brl
    FROM fact_order_items i
    JOIN dim_sellers s ON i.seller_id = s.seller_id
    WHERE i.order_status = 'delivered'
    GROUP BY s.seller_state, s.seller_id
),
ranked AS (
    SELECT *,
           RANK() OVER (PARTITION BY seller_state ORDER BY revenue_brl DESC) AS state_rank
    FROM seller_revenue
)
SELECT seller_state, state_rank, seller_id, orders, revenue_brl
FROM ranked
WHERE state_rank <= 3
ORDER BY seller_state, state_rank;

-- name: category_revenue_pareto
WITH category_revenue AS (
    SELECT p.product_category_name_english AS category,
           ROUND(SUM(i.price), 2)          AS revenue_brl
    FROM fact_order_items i
    JOIN dim_products p ON i.product_id = p.product_id
    WHERE i.order_status = 'delivered'
    GROUP BY p.product_category_name_english
)
SELECT category,
       revenue_brl,
       RANK() OVER (ORDER BY revenue_brl DESC) AS revenue_rank,
       ROUND(100.0 * revenue_brl / SUM(revenue_brl) OVER (), 2) AS share_pct,
       ROUND(100.0 * SUM(revenue_brl) OVER (ORDER BY revenue_brl DESC)
             / SUM(revenue_brl) OVER (), 2) AS cumulative_share_pct
FROM category_revenue
ORDER BY revenue_rank
LIMIT 15;

-- name: customers_above_average_spend
WITH customer_spend AS (
    SELECT c.customer_unique_id,
           COUNT(DISTINCT i.order_id) AS orders,
           ROUND(SUM(i.price), 2)     AS total_spend_brl
    FROM fact_order_items i
    JOIN dim_customers c ON i.customer_id = c.customer_id
    WHERE i.order_status = 'delivered'
    GROUP BY c.customer_unique_id
)
SELECT customer_unique_id,
       orders,
       total_spend_brl,
       ROUND((SELECT AVG(total_spend_brl) FROM customer_spend), 2) AS avg_spend_brl
FROM customer_spend
WHERE total_spend_brl > (SELECT AVG(total_spend_brl) FROM customer_spend)
ORDER BY total_spend_brl DESC
LIMIT 20;

-- name: delivery_performance_by_state
WITH delivered AS (
    SELECT c.customer_state,
           o.delivery_days,
           o.is_late
    FROM fact_orders o
    JOIN dim_customers c ON o.customer_id = c.customer_id
    WHERE o.order_status = 'delivered'
      AND o.delivery_days IS NOT NULL
),
state_stats AS (
    SELECT customer_state,
           COUNT(*)                         AS delivered_orders,
           ROUND(AVG(delivery_days), 1)     AS avg_delivery_days,
           ROUND(100.0 * AVG(is_late), 1)   AS late_pct
    FROM delivered
    GROUP BY customer_state
)
SELECT customer_state,
       delivered_orders,
       avg_delivery_days,
       late_pct,
       RANK() OVER (ORDER BY late_pct DESC) AS worst_late_rank
FROM state_stats
ORDER BY worst_late_rank;