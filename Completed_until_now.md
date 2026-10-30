# VeriQuery: Implementation Progress (Week 1, Days 1-2)

Trustworthy Analytics Agent: multi-agent RAG text-to-SQL with guardrails, evaluation and an LLM gateway.
Environment: Windows, Command Prompt, Docker Desktop, Python venv. `make` is not used; commands are run directly.

## Status at a glance

| Day | Scope | Status |
| --- | --- | --- |
| 1 | Repo scaffold, tooling, Postgres + pgvector | Done |
| 2 | Warehouse DDL (Alembic) + synthetic data generator | Done, 7/7 tests pass |
| 3 | Planted anomalies + data tests | Next |
| 4-6 | App schema and roles, knowledge sources, Pydantic schemas and FastAPI `/health` | Pending |

## Day 1: Scaffold

**Built**
- Full repo tree from section 2 of the plan: `src/analytics_agent/` (core, db, schemas, data_gen, gateway, rag, tools, agents, guardrails, evaluation, api), plus `configs/`, `data/`, `ui/`, `tests/`. Modules are stubs until their week.
- `pyproject.toml`: dependencies split into core, `agent` (LangGraph, LangChain, sqlglot, Presidio, LiteLLM), `ui` and `dev`. Ruff and pytest configured; markers `week1` to `week5` and `integration` registered.
- `docker-compose.yml`: `pgvector/pgvector:pg16` with a healthcheck. `docker/initdb/01_init.sql` enables the `vector` extension and creates the `warehouse` and `app` schemas.
- `.env.example`, `.gitignore`, `.pre-commit-config.yaml`, `.github/workflows/ci.yml` (lint + non-integration tests), a `Makefile` (kept for the final "fresh clone" checkpoint, unused on Windows).
- Starter configs: `settings.yaml`, `gateway_routing.yaml` (model names still `TBD`), `users.yaml`, and `guardrails/{input,sql_policy,output}.yaml`.

**Verified:** `pip install -e ".[dev,agent,ui]"`, `docker compose up -d --build` and `pytest -q` all ran cleanly.

## Day 2: Warehouse and data

**Built**
- **Alembic** (`alembic.ini`, `src/analytics_agent/db/migrations/`):
  - `env.py` reads `DATABASE_URL` from `.env` (not hard-coded in `alembic.ini`); `target_metadata` is `None` until Day 4.
  - `versions/0001_warehouse_schema.py`: raw-SQL DDL for the six `warehouse` tables, plus four indexes (orders by customer and timestamp, order_items by order, customers by channel). Includes a downgrade.
- **Generator** (`data_gen/generate_warehouse.py`): `generate(seed, n_customers)` builds the data in memory as plain lists (so Day 3 can modify it); `load()` truncates and bulk-loads with `COPY` in FK order.
  - Run: `python -m analytics_agent.data_gen.generate_warehouse` (defaults: seed 42, 20,000 customers).
- **Tests:**
  - `tests/unit/test_generator.py`: determinism, seed sensitivity, internal referential integrity (no DB needed).
  - `tests/integration/test_warehouse_db.py`: row counts, no orphan foreign keys, all 4 regions and 5 channels present.

**Data profile (seed 42)**
- Span: 2024-01-01 to 2025-12-31. Signups end 2025-09-30, so Q3 2025 cohorts have full 90-day windows.
- About 20,000 customers, 288 products (6 categories), about 146,849 orders, about 264,004 order items, 2,924 marketing rows, plus returns.
- Customers fall into three loyalty segments (repeat probability and gap between orders), tuned so volume and repeat rate land near plan.
- Baseline 90-day repeat rate for the Q3 2025 first-order cohort is about 45% overall:

| Channel | Cohort | repeat_90d |
| --- | --- | --- |
| email | 410 | ~0.43 |
| organic | 899 | ~0.47 |
| paid_search | 720 | ~0.41 |
| paid_social | 607 | ~0.47 |
| referral | 296 | ~0.46 |

## Changes and fixes along the way

1. **Lint:** added `ignore = ["E501"]` under `[tool.ruff.lint]` so long data-table lines don't fail ruff.
2. **Alembic setup:** ran `alembic init` into the existing migrations folder and created `versions/` by hand.
3. **Data calibration:** the first segment parameters gave only about 73k orders. I tuned them against the plan's 150k target and a realistic repeat rate (~45%).
4. **Database did not exist:** `alembic upgrade head` failed with `database "analytics" does not exist`. The init script had not run on an existing volume. Fixed with `docker compose down -v`, then `docker compose up -d`. If another Postgres holds port 5432, remap to 5433 in `docker-compose.yml` and `.env`.
5. **`psql` command:** `docker compose exec` takes the service name (`db`); `docker exec` takes the container name (`analytics_db`).
6. **Repeat-rate query bug:** the first version averaged a NULL-able expression, so non-repeaters were ignored and rates looked like ~95%. Fixed with `COALESCE(..., false)`. This is the same class of silent error the critic agent and evaluation harness are meant to catch later.

## Checkpoint 1: progress

| Criterion | State |
| --- | --- |
| Everything starts (`docker compose up`) | Met |
| Tests pass (`pytest -m week1`) | Met for Days 1-2 (7/7) |
| Planted Q3 drop for `paid_social` + `Home & Kitchen` visible by hand | Pending (Day 3) |
| `agent_ro` can read approved tables, cannot write or read `email` | Pending (Day 4) |

## Useful commands (cmd)

```bat
docker compose up -d
alembic upgrade head
python -m analytics_agent.data_gen.generate_warehouse
pytest -q
docker compose exec db psql -U postgres -d analytics
```

## What's next

- **Day 3: Planted anomalies.** Implement `plant_anomalies.py` and write `data/ground_truth/planted_anomalies.json`:
  - True cause: Q3 repeat rate drops for `paid_social` customers who bought `Home & Kitchen`.
  - Red herring: a visible returns spike in `Electronics` that does not affect repeat purchase.
  - Data quirk: one week of duplicated `order_items` rows (tests the critic's double-counting check).
  - Add data tests proving each anomaly exists when queried by hand.
- **Day 4:** app schema as SQLAlchemy models and migrations; create `agent_rw` and `agent_ro` roles (`agent_ro`: SELECT on approved tables only, no `email`/`phone`, `statement_timeout` set).
- **Day 5:** knowledge sources: data dictionary YAMLs, `metric_definitions.yaml`, 8-10 analyst notes including known data quirks (the duplicate week and the NULL-averaging trap are good candidates).
- **Day 6:** Pydantic schemas, config loader, structured logging, FastAPI `/health`, then Checkpoint 1.
