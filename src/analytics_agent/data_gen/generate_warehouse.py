"""Synthetic e-commerce warehouse generator (Week 1, Day 2).

Deterministic for a given seed. `generate()` builds everything in memory (plain lists,
so Day 3's plant_anomalies.py can modify it); `load()` bulk-loads it into Postgres.

Run:  python -m analytics_agent.data_gen.generate_warehouse --seed 42
"""

from __future__ import annotations

import argparse
import os
import random
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from faker import Faker

START = date(2024, 1, 1)
SIGNUP_END = date(2025, 9, 30)
END = date(2025, 12, 31)

REGIONS = (["North", "South", "East", "West"], [0.28, 0.24, 0.26, 0.22])
ACQ_CHANNELS = (
    ["organic", "paid_search", "paid_social", "email", "referral"],
    [0.30, 0.25, 0.20, 0.15, 0.10],
)
SALES_CHANNELS = (["web", "mobile_app", "marketplace"], [0.50, 0.38, 0.12])
ORDER_STATUS = (["completed", "cancelled", "refunded"], [0.92, 0.04, 0.04])
RETURN_REASONS = ["defective", "wrong_item", "not_as_described", "changed_mind", "too_late"]

# category -> (item-mix weight, {subcategory: (min_price, max_price)})
CATALOG: dict[str, tuple[float, dict[str, tuple[int, int]]]] = {
    "Electronics": (
        0.18,
        {"Phones": (150, 900), "Audio": (20, 300), "Laptops": (400, 1800), "Accessories": (8, 60)},
    ),
    "Home & Kitchen": (
        0.22,
        {"Cookware": (15, 150), "Appliances": (40, 400), "Storage": (8, 70), "Decor": (10, 120)},
    ),
    "Apparel": (
        0.25,
        {"Tops": (10, 60), "Bottoms": (15, 90), "Outerwear": (40, 220), "Footwear": (25, 150)},
    ),
    "Beauty": (
        0.15,
        {"Skincare": (8, 90), "Makeup": (6, 60), "Haircare": (6, 50), "Fragrance": (20, 140)},
    ),
    "Sports": (
        0.12,
        {"Fitness": (10, 200), "Outdoor": (15, 250), "Team Sports": (10, 120), "Yoga": (8, 80)},
    ),
    "Books": (
        0.08,
        {"Fiction": (6, 25), "Non-fiction": (8, 35), "Textbooks": (20, 120), "Kids": (5, 20)},
    ),
}
ADJECTIVES = [
    "Classic",
    "Pro",
    "Eco",
    "Smart",
    "Ultra",
    "Basic",
    "Premium",
    "Compact",
    "Deluxe",
    "Essential",
]

# Customer loyalty segments: (probability of placing another order, mean gap in days, share)
SEGMENTS = [(0.10, 70, 0.50), (0.80, 40, 0.28), (0.985, 12, 0.22)]


@dataclass
class Warehouse:
    customers: list[list] = field(default_factory=list)
    products: list[list] = field(default_factory=list)
    orders: list[list] = field(default_factory=list)
    order_items: list[list] = field(default_factory=list)
    returns: list[list] = field(default_factory=list)
    marketing_spend: list[list] = field(default_factory=list)


def _daterange(start: date, end: date):
    for i in range((end - start).days + 1):
        yield start + timedelta(days=i)


def _gen_products(rng: random.Random) -> tuple[list[list], dict[str, list[list]]]:
    products: list[list] = []
    by_cat: dict[str, list[list]] = {c: [] for c in CATALOG}
    pid = 1
    for cat, (_, subs) in CATALOG.items():
        per_sub = 12
        for sub, (lo, hi) in subs.items():
            for _ in range(per_sub):
                price = round(rng.uniform(lo, hi), 2)
                cost = round(price * rng.uniform(0.45, 0.75), 2)
                name = f"{rng.choice(ADJECTIVES)} {sub} {pid}"
                row = [pid, name, cat, sub, price, cost]
                products.append(row)
                by_cat[cat].append(row)
                pid += 1
    return products, by_cat


def _gen_customers(rng: random.Random, fake: Faker, n: int) -> list[list]:
    span = (SIGNUP_END - START).days
    rows = []
    for cid in range(1, n + 1):
        signup = START + timedelta(days=rng.randint(0, span))
        region = rng.choices(*REGIONS)[0]
        channel = rng.choices(*ACQ_CHANNELS)[0]
        email = f"{fake.first_name().lower()}.{fake.last_name().lower()}{cid}@example.com"
        rows.append([cid, signup, region, channel, email, fake.phone_number()])
    return rows


def _order_dates(rng: random.Random, signup: date) -> list[date]:
    first = signup + timedelta(days=rng.randint(0, 10))
    if first > END:
        return []
    p, gap, _ = rng.choices(SEGMENTS, weights=[s[2] for s in SEGMENTS])[0]
    dates, d = [first], first
    while rng.random() < p:
        d = d + timedelta(days=1 + int(rng.expovariate(1 / gap)))
        if d > END:
            break
        dates.append(d)
    return dates


def generate(seed: int = 42, n_customers: int = 20_000) -> Warehouse:
    rng = random.Random(seed)
    Faker.seed(seed)
    fake = Faker("en_US")
    wh = Warehouse()

    wh.products, by_cat = _gen_products(rng)
    wh.customers = _gen_customers(rng, fake, n_customers)

    cats = list(CATALOG)
    cat_w = [CATALOG[c][0] for c in cats]
    order_id = item_id = return_id = 0

    for cid, signup, region, _channel, _email, _phone in wh.customers:
        for d in _order_dates(rng, signup):
            order_id += 1
            ts = datetime(
                d.year, d.month, d.day, rng.randint(7, 22), rng.randint(0, 59), rng.randint(0, 59)
            )
            status = rng.choices(*ORDER_STATUS)[0]
            subtotal = 0.0
            items = []
            for _ in range(rng.choices([1, 2, 3, 4], [0.50, 0.28, 0.14, 0.08])[0]):
                prod = rng.choice(by_cat[rng.choices(cats, cat_w)[0]])
                qty = rng.choices([1, 2, 3], [0.80, 0.15, 0.05])[0]
                item_id += 1
                items.append([item_id, order_id, prod[0], qty, prod[4]])
                subtotal += qty * prod[4]
            discount = round(subtotal * rng.choice([0, 0, 0, 0.05, 0.10, 0.15, 0.20]), 2)
            wh.orders.append(
                [
                    order_id,
                    cid,
                    ts,
                    status,
                    rng.choices(*SALES_CHANNELS)[0],
                    region,
                    round(subtotal - discount, 2),
                    discount,
                ]
            )
            wh.order_items.extend(items)

            p_return = {"completed": 0.05, "refunded": 0.90, "cancelled": 0.0}[status]
            for it in items:
                if rng.random() < p_return:
                    return_id += 1
                    rts = ts + timedelta(days=rng.randint(2, 30), hours=rng.randint(0, 23))
                    wh.returns.append([return_id, it[0], rts, rng.choice(RETURN_REASONS)])

    base = {"paid_search": 900, "paid_social": 700, "email": 150, "referral": 100}
    for d in _daterange(START, END):
        for ch, b in base.items():
            spend = round(b * rng.uniform(0.8, 1.2), 2)
            impressions = int(spend * rng.uniform(40, 80))
            clicks = int(impressions * rng.uniform(0.01, 0.03))
            wh.marketing_spend.append([d, ch, spend, impressions, clicks])
    return wh


TABLES = {  # load order = FK order
    "customers": ["customer_id", "signup_date", "region", "acquisition_channel", "email", "phone"],
    "products": ["product_id", "name", "category", "subcategory", "price", "cost"],
    "orders": [
        "order_id",
        "customer_id",
        "order_ts",
        "status",
        "channel",
        "region",
        "total_amount",
        "discount_amount",
    ],
    "order_items": ["order_item_id", "order_id", "product_id", "quantity", "unit_price"],
    "returns": ["return_id", "order_item_id", "return_ts", "reason"],
    "marketing_spend": ["date", "channel", "spend", "impressions", "clicks"],
}


def load(wh: Warehouse, dsn: str) -> None:
    import psycopg

    with psycopg.connect(dsn) as conn, conn.cursor() as cur:
        cur.execute(
            "TRUNCATE warehouse.returns, warehouse.order_items, warehouse.orders, "
            "warehouse.marketing_spend, warehouse.products, warehouse.customers"
        )
        for table, cols in TABLES.items():
            with cur.copy(f"COPY warehouse.{table} ({', '.join(cols)}) FROM STDIN") as cp:
                for row in getattr(wh, table):
                    cp.write_row(row)
        conn.commit()


def main() -> None:
    from dotenv import load_dotenv

    load_dotenv()
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=int(os.getenv("DATA_SEED", "42")))
    ap.add_argument("--customers", type=int, default=20_000)
    args = ap.parse_args()

    wh = generate(args.seed, args.customers)
    dsn = os.environ["DATABASE_URL"].replace("postgresql+psycopg://", "postgresql://")
    load(wh, dsn)
    print({t: len(getattr(wh, t)) for t in TABLES})


if __name__ == "__main__":
    main()
