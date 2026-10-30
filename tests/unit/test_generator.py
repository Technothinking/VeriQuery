import pytest

from analytics_agent.data_gen.generate_warehouse import generate

pytestmark = pytest.mark.week1


def test_generation_is_deterministic():
    a, b = generate(7, 300), generate(7, 300)
    assert a.customers == b.customers
    assert a.orders == b.orders
    assert a.order_items == b.order_items


def test_different_seed_differs():
    assert generate(1, 300).orders != generate(2, 300).orders


def test_internal_referential_integrity():
    wh = generate(7, 300)
    cust = {c[0] for c in wh.customers}
    prod = {p[0] for p in wh.products}
    orders = {o[0] for o in wh.orders}
    items = {i[0] for i in wh.order_items}
    assert all(o[1] in cust for o in wh.orders)
    assert all(i[1] in orders and i[2] in prod for i in wh.order_items)
    assert all(r[1] in items for r in wh.returns)
