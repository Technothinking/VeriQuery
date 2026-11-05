\echo '== 1. Q3 2025 90-day repeat rate by channel group x first-order category =='
WITH first_orders AS (
  SELECT DISTINCT ON (customer_id) customer_id, order_id, order_ts
  FROM warehouse.orders ORDER BY customer_id, order_ts, order_id
),
cohort AS (
  SELECT f.customer_id, c.acquisition_channel,
    EXISTS (SELECT 1 FROM warehouse.order_items i JOIN warehouse.products p USING (product_id)
            WHERE i.order_id = f.order_id AND p.category = 'Home & Kitchen') AS has_home_kitchen,
    EXISTS (SELECT 1 FROM warehouse.orders o WHERE o.customer_id = f.customer_id
            AND o.order_ts > f.order_ts AND o.order_ts <= f.order_ts + interval '90 days') AS repeated
  FROM first_orders f JOIN warehouse.customers c USING (customer_id)
  WHERE f.order_ts >= '2025-07-01' AND f.order_ts < '2025-10-01'
)
SELECT (acquisition_channel = 'paid_social') AS paid_social, has_home_kitchen,
       count(*) AS cohort, round(avg(repeated::int)::numeric, 3) AS repeat_90d
FROM cohort GROUP BY 1, 2 ORDER BY 1, 2;

\echo '== 2. Item return rate by month: Electronics vs everything else =='
SELECT to_char(date_trunc('month', o.order_ts), 'YYYY-MM') AS month,
       round(100.0 * count(r.return_id) FILTER (WHERE p.category = 'Electronics')
             / NULLIF(count(*) FILTER (WHERE p.category = 'Electronics'), 0), 1) AS electronics_pct,
       round(100.0 * count(r.return_id) FILTER (WHERE p.category <> 'Electronics')
             / NULLIF(count(*) FILTER (WHERE p.category <> 'Electronics'), 0), 1) AS other_pct
FROM warehouse.order_items i
JOIN warehouse.orders o USING (order_id)
JOIN warehouse.products p USING (product_id)
LEFT JOIN warehouse.returns r USING (order_item_id)
WHERE o.order_ts >= '2025-05-01' AND o.order_ts < '2025-11-01'
GROUP BY 1 ORDER BY 1;

\echo '== 3. Item-level revenue / order-level revenue by week (expect ~2.0 for 2025-09-08) =='
WITH item_rev AS (
  SELECT order_id, sum(quantity * unit_price) AS item_value
  FROM warehouse.order_items GROUP BY order_id
)
SELECT date_trunc('week', o.order_ts)::date AS week,
       round((sum(r.item_value) / sum(o.total_amount + o.discount_amount))::numeric, 2) AS ratio
FROM warehouse.orders o
JOIN item_rev r USING (order_id)
WHERE o.order_ts >= '2025-08-18' AND o.order_ts < '2025-09-29'
GROUP BY 1 ORDER BY 1;
