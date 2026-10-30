"""warehouse schema

Revision ID: 0001
Revises:
"""

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

STATEMENTS = [
    "CREATE SCHEMA IF NOT EXISTS warehouse",
    """CREATE TABLE warehouse.customers (
        customer_id BIGINT PRIMARY KEY,
        signup_date DATE NOT NULL,
        region TEXT NOT NULL,
        acquisition_channel TEXT NOT NULL,
        email TEXT,
        phone TEXT
    )""",
    """CREATE TABLE warehouse.products (
        product_id BIGINT PRIMARY KEY,
        name TEXT, category TEXT, subcategory TEXT,
        price NUMERIC(10,2), cost NUMERIC(10,2)
    )""",
    """CREATE TABLE warehouse.orders (
        order_id BIGINT PRIMARY KEY,
        customer_id BIGINT REFERENCES warehouse.customers,
        order_ts TIMESTAMP NOT NULL,
        status TEXT,
        channel TEXT, region TEXT,
        total_amount NUMERIC(12,2), discount_amount NUMERIC(12,2)
    )""",
    """CREATE TABLE warehouse.order_items (
        order_item_id BIGINT PRIMARY KEY,
        order_id BIGINT REFERENCES warehouse.orders,
        product_id BIGINT REFERENCES warehouse.products,
        quantity INT, unit_price NUMERIC(10,2)
    )""",
    """CREATE TABLE warehouse.returns (
        return_id BIGINT PRIMARY KEY,
        order_item_id BIGINT REFERENCES warehouse.order_items,
        return_ts TIMESTAMP, reason TEXT
    )""",
    """CREATE TABLE warehouse.marketing_spend (
        date DATE, channel TEXT, spend NUMERIC(12,2),
        impressions BIGINT, clicks BIGINT,
        PRIMARY KEY (date, channel)
    )""",
    "CREATE INDEX ix_orders_customer ON warehouse.orders (customer_id)",
    "CREATE INDEX ix_orders_ts ON warehouse.orders (order_ts)",
    "CREATE INDEX ix_items_order ON warehouse.order_items (order_id)",
    "CREATE INDEX ix_customers_channel ON warehouse.customers (acquisition_channel)",
]


def upgrade() -> None:
    for stmt in STATEMENTS:
        op.execute(stmt)


def downgrade() -> None:
    for t in ["returns", "order_items", "orders", "marketing_spend", "products", "customers"]:
        op.execute(f"DROP TABLE IF EXISTS warehouse.{t}")
