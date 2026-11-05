from collections import Counter

import pytest

from analytics_agent.data_gen import plant_anomalies as pa
from analytics_agent.data_gen.generate_warehouse import generate

pytestmark = pytest.mark.week1

SEG = "paid_social|home_kitchen"


def _by_id(truth, rec_id):
    return next(r for r in truth if r["id"] == rec_id)


@pytest.fixture(scope="module")
def planted():
    wh = generate(7, 10_000)
    before = pa.repeat_rates(wh, pa.Q3_START, pa.Q4_START)
    elec_before = pa.electronics_return_rate(wh, pa.SPIKE_START, pa.SPIKE_END)
    truth = pa.plant(wh, 7)
    after = pa.repeat_rates(wh, pa.Q3_START, pa.Q4_START)
    elec_after = pa.electronics_return_rate(wh, pa.SPIKE_START, pa.SPIKE_END)
    return {
        "wh": wh,
        "before": before,
        "after": after,
        "truth": truth,
        "elec_before": elec_before,
        "elec_after": elec_after,
    }


def test_planting_is_deterministic():
    a, b = generate(7, 1_500), generate(7, 1_500)
    ta, tb = pa.plant(a, 7), pa.plant(b, 7)
    assert a.orders == b.orders
    assert a.order_items == b.order_items
    assert a.returns == b.returns
    assert ta == tb


def test_repeat_rate_drops_only_for_target_segment(planted):
    before, after = planted["before"], planted["after"]
    assert after[SEG]["cohort"] == before[SEG]["cohort"] >= 50
    assert before[SEG]["repeat_90d"] > 0.35
    assert after[SEG]["repeat_90d"] < 0.5 * before[SEG]["repeat_90d"]
    # every other segment must be exactly unchanged
    for key in before:
        if key != SEG:
            assert after[key] == before[key]


def test_electronics_return_spike_is_visible(planted):
    assert planted["elec_before"] < 0.12
    assert planted["elec_after"] > 0.25


def test_duplicate_week_doubles_items(planted):
    wh = planted["wh"]
    in_week = {o[0] for o in wh.orders if pa.DUP_START <= o[2] < pa.DUP_END}
    per_order = Counter(i[1] for i in wh.order_items if i[1] in in_week)
    assert in_week and all(n % 2 == 0 for n in per_order.values())
    rec = _by_id(planted["truth"], "duplicated_order_items_week")
    assert rec["parameters"]["duplicated_rows"] == sum(per_order.values()) // 2


def test_integrity_after_planting(planted):
    wh = planted["wh"]
    cust = {c[0] for c in wh.customers}
    prod = {p[0] for p in wh.products}
    orders = {o[0] for o in wh.orders}
    item_ids = [i[0] for i in wh.order_items]
    return_ids = [r[0] for r in wh.returns]
    assert all(o[1] in cust for o in wh.orders)
    assert all(i[1] in orders and i[2] in prod for i in wh.order_items)
    assert len(item_ids) == len(set(item_ids))
    assert len(return_ids) == len(set(return_ids))
    items = set(item_ids)
    assert all(r[1] in items for r in wh.returns)
