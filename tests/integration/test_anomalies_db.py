import os

import psycopg
import pytest
from dotenv import load_dotenv

pytestmark = [pytest.mark.week1, pytest.mark.integration]
load_dotenv()


@pytest.fixture(scope="module")
def cur():
    dsn = os.environ["DATABASE_URL"].replace("postgresql+psycopg://", "postgresql://")
    with psycopg.connect(dsn) as conn, conn.cursor() as c:
        yield c


REPEAT_SQL = """
WITH first_orders AS (
  SELECT DISTINCT ON (customer_id) customer_id, order_id, order_ts
  FROM warehouse.orders
  ORDER BY customer_id, order_ts, order_id
),
cohort AS (
  SELECT f.customer_id, c.acquisition_channel,
    EXISTS (SELECT 1 FROM warehouse.order_items i
            JOIN warehouse.products p USING (product_id)
            WHERE i.order_id = f.order_id AND p.category = 'Home & Kitchen') AS has_hk,
    EXISTS (SELECT 1 FROM warehouse.orders o
            WHERE o.customer_id = f.customer_id
              AND o.order_ts > f.order_ts
              AND o.order_ts <= f.order_ts + interval '90 days') AS repeated
  FROM first_orders f
  JOIN warehouse.customers c USING (customer_id)
  WHERE f.order_ts >= %s AND f.order_ts < %s
)
SELECT (acquisition_channel = 'paid_social') AS paid_social, has_hk,
       count(*) AS n, avg(repeated::int)::float AS rate
FROM cohort GROUP BY 1, 2
"""


def repeat_rates(cur, start, end):
    cur.execute(REPEAT_SQL, (start, end))
    return {(ps, hk): (n, rate) for ps, hk, n, rate in cur.fetchall()}


def test_q3_repeat_drop_for_paid_social_home_kitchen(cur):
    q3 = repeat_rates(cur, "2025-07-01", "2025-10-01")
    q2 = repeat_rates(cur, "2025-04-01", "2025-07-01")
    n, rate = q3[(True, True)]
    assert n >= 100
    assert rate < 0.20
    assert q2[(True, True)][1] > 0.35  # same segment was healthy in Q2
    for seg in [(True, False), (False, True), (False, False)]:
        assert q3[seg][1] > 0.35  # every other Q3 segment is healthy


RETURN_SQL = """
SELECT (p.category = 'Electronics') AS is_elec,
       (o.order_ts >= '2025-07-01' AND o.order_ts < '2025-09-01') AS in_spike,
       count(*) AS items, count(r.return_id) AS returns
FROM warehouse.order_items i
JOIN warehouse.orders o USING (order_id)
JOIN warehouse.products p USING (product_id)
LEFT JOIN warehouse.returns r USING (order_item_id)
GROUP BY 1, 2
"""


def test_electronics_return_spike(cur):
    cur.execute(RETURN_SQL)
    rate = {(e, s): ret / items for e, s, items, ret in cur.fetchall()}
    assert rate[(True, True)] > 0.25  # Electronics inside the window
    assert rate[(True, False)] < 0.12  # Electronics outside the window
    assert rate[(False, True)] < 0.12  # other categories in the window


DUP_SQL = """
WITH item_rev AS (
  SELECT order_id, count(*) AS n_items, sum(quantity * unit_price) AS item_value
  FROM warehouse.order_items GROUP BY order_id
)
SELECT count(*) AS orders,
       sum(r.n_items)::float AS items,
       sum(r.item_value)::float AS item_value,
       sum(o.total_amount + o.discount_amount)::float AS order_value
FROM warehouse.orders o
JOIN item_rev r USING (order_id)
WHERE o.order_ts >= %(s)s AND o.order_ts < %(e)s
"""


def week_stats(cur, start, end):
    cur.execute(DUP_SQL, {"s": start, "e": end})
    orders, items, item_value, order_value = cur.fetchone()
    return items / orders, item_value / order_value


def test_duplicate_week_inflates_items_and_revenue(cur):
    normal_ipo, normal_ratio = week_stats(cur, "2025-09-01", "2025-09-08")
    dup_ipo, dup_ratio = week_stats(cur, "2025-09-08", "2025-09-15")
    assert dup_ipo / normal_ipo > 1.8
    assert 0.95 < normal_ratio < 1.05
    assert dup_ratio > 1.8
