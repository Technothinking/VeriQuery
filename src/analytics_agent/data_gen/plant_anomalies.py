"""Plant ground-truth anomalies into the synthetic warehouse (Week 1, Day 3).

Three anomalies, applied in memory to the Warehouse built by generate():
  1. TRUE CAUSE   - Q3 2025: 90-day repeat rate collapses for paid_social customers
                    whose first order contains a Home & Kitchen item.
  2. RED HERRING  - Jul-Aug 2025: Electronics return-rate spike (orders untouched,
                    so repeat purchase is unaffected).
  3. DATA QUIRK   - Orders placed 2025-09-08..2025-09-14 have every order_item
                    duplicated (new order_item_id, same content).

Run:  python -m analytics_agent.data_gen.plant_anomalies --seed 42
"""

from __future__ import annotations

import argparse
import json
import os
import random
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

from analytics_agent.data_gen.generate_warehouse import TABLES, Warehouse, generate, load

GROUND_TRUTH_PATH = (
    Path(__file__).resolve().parents[3] / "data" / "ground_truth" / "planted_anomalies.json"
)

HOME_KITCHEN = "Home & Kitchen"
ELECTRONICS = "Electronics"
REPEAT_WINDOW = timedelta(days=90)

# 1. true cause
Q2_START = datetime(2025, 4, 1)
Q3_START = datetime(2025, 7, 1)
Q4_START = datetime(2025, 10, 1)
DROP_PROB = 0.80

# 2. red herring
BASE_START = datetime(2025, 1, 1)
SPIKE_START = datetime(2025, 7, 1)
SPIKE_END = datetime(2025, 9, 1)  # exclusive
SPIKE_PROB = 0.30
SPIKE_REASONS = (
    ["defective", "not_as_described", "wrong_item", "changed_mind", "too_late"],
    [0.60, 0.20, 0.10, 0.07, 0.03],
)

# 3. data quirk
DUP_START = datetime(2025, 9, 8)
DUP_END = datetime(2025, 9, 15)  # exclusive


# ---------------------------------------------------------------- helpers
def _first_orders(wh: Warehouse) -> dict[int, list]:
    first: dict[int, list] = {}
    for o in wh.orders:
        cur = first.get(o[1])
        if cur is None or o[2] < cur[2]:
            first[o[1]] = o
    return first


def _items_by_order(wh: Warehouse) -> dict[int, list]:
    d: dict[int, list] = defaultdict(list)
    for it in wh.order_items:
        d[it[1]].append(it)
    return d


def repeat_rates(wh: Warehouse, start: datetime, end: datetime) -> dict[str, dict]:
    """90-day repeat rate for customers whose first order is in [start, end),
    split by (paid_social vs other) x (first order has Home & Kitchen vs not)."""
    first = _first_orders(wh)
    items = _items_by_order(wh)
    category = {p[0]: p[2] for p in wh.products}
    channel = {c[0]: c[3] for c in wh.customers}
    order_ts: dict[int, list] = defaultdict(list)
    for o in wh.orders:
        order_ts[o[1]].append(o[2])

    counts: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for cid, fo in first.items():
        t0 = fo[2]
        if not (start <= t0 < end):
            continue
        has_hk = any(category[i[2]] == HOME_KITCHEN for i in items[fo[0]])
        repeated = any(t0 < t <= t0 + REPEAT_WINDOW for t in order_ts[cid])
        ch = "paid_social" if channel[cid] == "paid_social" else "other_channels"
        cat = "home_kitchen" if has_hk else "other_categories"
        key = f"{ch}|{cat}"
        counts[key][0] += 1
        counts[key][1] += int(repeated)
    return {k: {"cohort": n, "repeat_90d": round(r / n, 4)} for k, (n, r) in sorted(counts.items())}


def electronics_return_rate(wh: Warehouse, start: datetime, end: datetime) -> float:
    """Returned items / items for Electronics items ordered in [start, end)."""
    category = {p[0]: p[2] for p in wh.products}
    order_ts = {o[0]: o[2] for o in wh.orders}
    returned = {r[1] for r in wh.returns}
    n = k = 0
    for it in wh.order_items:
        if category[it[2]] == ELECTRONICS and start <= order_ts[it[1]] < end:
            n += 1
            k += int(it[0] in returned)
    return round(k / n, 4) if n else 0.0


# ---------------------------------------------------------------- anomalies
def _plant_repeat_drop(wh: Warehouse, rng: random.Random) -> tuple[int, int]:
    first = _first_orders(wh)
    items = _items_by_order(wh)
    category = {p[0]: p[2] for p in wh.products}
    channel = {c[0]: c[3] for c in wh.customers}

    affected: set[int] = set()
    for cid, fo in first.items():
        t0 = fo[2]
        if channel[cid] != "paid_social" or not (Q3_START <= t0 < Q4_START):
            continue
        if not any(category[i[2]] == HOME_KITCHEN for i in items[fo[0]]):
            continue
        if rng.random() < DROP_PROB:
            affected.add(cid)

    drop_orders = {
        o[0]
        for o in wh.orders
        if o[1] in affected and first[o[1]][2] < o[2] <= first[o[1]][2] + REPEAT_WINDOW
    }
    drop_items = {i[0] for i in wh.order_items if i[1] in drop_orders}
    wh.orders = [o for o in wh.orders if o[0] not in drop_orders]
    wh.order_items = [i for i in wh.order_items if i[0] not in drop_items]
    wh.returns = [r for r in wh.returns if r[1] not in drop_items]
    return len(affected), len(drop_orders)


def _plant_electronics_returns(wh: Warehouse, rng: random.Random) -> int:
    category = {p[0]: p[2] for p in wh.products}
    order_by_id = {o[0]: o for o in wh.orders}
    returned = {r[1] for r in wh.returns}
    next_id = max((r[0] for r in wh.returns), default=0) + 1
    added = 0
    for it in wh.order_items:
        o = order_by_id[it[1]]
        if category[it[2]] != ELECTRONICS or o[3] != "completed" or it[0] in returned:
            continue
        if not (SPIKE_START <= o[2] < SPIKE_END):
            continue
        if rng.random() < SPIKE_PROB:
            reason = rng.choices(*SPIKE_REASONS)[0]
            rts = o[2] + timedelta(days=rng.randint(2, 30), hours=rng.randint(0, 23))
            wh.returns.append([next_id, it[0], rts, reason])
            next_id += 1
            added += 1
    return added


def _plant_duplicate_week(wh: Warehouse) -> int:
    in_week = {o[0] for o in wh.orders if DUP_START <= o[2] < DUP_END}
    next_id = max((i[0] for i in wh.order_items), default=0) + 1
    dups = []
    for it in wh.order_items:
        if it[1] in in_week:
            dups.append([next_id, it[1], it[2], it[3], it[4]])
            next_id += 1
    wh.order_items.extend(dups)
    return len(dups)


# ---------------------------------------------------------------- orchestration
def plant(wh: Warehouse, seed: int = 42) -> list[dict]:
    """Mutate `wh` in place; return the ground-truth records."""
    seg = "paid_social|home_kitchen"
    rates_before = repeat_rates(wh, Q3_START, Q4_START)
    ret_base = electronics_return_rate(wh, BASE_START, SPIKE_START)
    ret_window_before = electronics_return_rate(wh, SPIKE_START, SPIKE_END)

    n_customers, n_orders_removed = _plant_repeat_drop(wh, random.Random(seed * 10 + 1))
    rates_after = repeat_rates(wh, Q3_START, Q4_START)
    rates_q2 = repeat_rates(wh, Q2_START, Q3_START)

    n_returns_added = _plant_electronics_returns(wh, random.Random(seed * 10 + 2))
    ret_window_after = electronics_return_rate(wh, SPIKE_START, SPIKE_END)

    n_dup_rows = _plant_duplicate_week(wh)

    return [
        {
            "id": "repeat_drop_paid_social_home_kitchen",
            "role": "true_cause",
            "description": (
                "In Q3 2025 the 90-day repeat purchase rate collapses for customers "
                "acquired via paid_social whose first order contains a Home & Kitchen item."
            ),
            "metric": "repeat_purchase_rate_90d",
            "period": {"start": "2025-07-01", "end": "2025-09-30"},
            "filters": {
                "acquisition_channel": "paid_social",
                "first_order_category": HOME_KITCHEN,
            },
            "parameters": {
                "drop_probability": DROP_PROB,
                "customers_affected": n_customers,
                "orders_removed": n_orders_removed,
            },
            "measured": {
                "segment_before": rates_before.get(seg),
                "segment_after": rates_after.get(seg),
                "segment_same_channel_category_q2_2025": rates_q2.get(seg),
                "all_segments_q3_after": rates_after,
            },
        },
        {
            "id": "electronics_return_spike",
            "role": "red_herring",
            "description": (
                "Electronics return rate spikes in Jul-Aug 2025. Orders are untouched, so "
                "this does not explain the repeat purchase drop."
            ),
            "metric": "return_rate_items",
            "period": {"start": "2025-07-01", "end": "2025-08-31"},
            "filters": {"category": ELECTRONICS},
            "parameters": {
                "extra_return_probability": SPIKE_PROB,
                "returns_added": n_returns_added,
            },
            "measured": {
                "rate_jan_jun_2025": ret_base,
                "rate_in_window_before": ret_window_before,
                "rate_in_window_after": ret_window_after,
            },
        },
        {
            "id": "duplicated_order_items_week",
            "role": "data_quirk",
            "description": (
                "Every order_item of orders placed 2025-09-08..2025-09-14 is duplicated "
                "(new order_item_id, same order_id/product/quantity/price). Item-level revenue "
                "is about 2x orders.total_amount + discount_amount for that week."
            ),
            "metric": "item_level_revenue",
            "period": {"start": "2025-09-08", "end": "2025-09-14"},
            "filters": {},
            "parameters": {"duplicated_rows": n_dup_rows},
            "measured": {},
        },
    ]


def write_ground_truth(records: list[dict], path: Path = GROUND_TRUTH_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(records, indent=2, default=str) + "\n", encoding="utf-8")


def main() -> None:
    from dotenv import load_dotenv

    load_dotenv()
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=int(os.getenv("DATA_SEED", "42")))
    ap.add_argument("--customers", type=int, default=20_000)
    ap.add_argument("--no-load", action="store_true", help="skip loading into Postgres")
    args = ap.parse_args()

    wh = generate(args.seed, args.customers)
    records = plant(wh, args.seed)
    write_ground_truth(records)
    if not args.no_load:
        dsn = os.environ["DATABASE_URL"].replace("postgresql+psycopg://", "postgresql://")
        load(wh, dsn)
    print({t: len(getattr(wh, t)) for t in TABLES})
    print(f"ground truth written to {GROUND_TRUTH_PATH}")


if __name__ == "__main__":
    main()
