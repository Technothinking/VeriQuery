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


def scalar(cur, sql):
    cur.execute(sql)
    return cur.fetchone()[0]


def test_row_counts(cur):
    assert scalar(cur, "SELECT count(*) FROM warehouse.customers") == 20_000
    assert 120_000 <= scalar(cur, "SELECT count(*) FROM warehouse.orders") <= 180_000
    assert scalar(cur, "SELECT count(*) FROM warehouse.products") > 200
    assert scalar(cur, "SELECT count(*) FROM warehouse.order_items") > scalar(
        cur, "SELECT count(*) FROM warehouse.orders"
    )


def test_no_orphan_foreign_keys(cur):
    assert (
        scalar(
            cur,
            """SELECT count(*) FROM warehouse.orders o
        LEFT JOIN warehouse.customers c USING (customer_id) WHERE c.customer_id IS NULL""",
        )
        == 0
    )
    assert (
        scalar(
            cur,
            """SELECT count(*) FROM warehouse.order_items i
        LEFT JOIN warehouse.orders o USING (order_id) WHERE o.order_id IS NULL""",
        )
        == 0
    )
    assert (
        scalar(
            cur,
            """SELECT count(*) FROM warehouse.returns r
        LEFT JOIN warehouse.order_items i USING (order_item_id) WHERE i.order_item_id IS NULL""",
        )
        == 0
    )


def test_all_regions_and_channels_present(cur):
    assert scalar(cur, "SELECT count(DISTINCT region) FROM warehouse.customers") == 4
    assert scalar(cur, "SELECT count(DISTINCT acquisition_channel) FROM warehouse.customers") == 5
