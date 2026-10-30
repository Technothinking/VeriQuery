.PHONY: up down test lint fmt install migrate
install:
	pip install -e ".[dev,agent,ui]"
up:
	docker compose up -d --build
down:
	docker compose down
test:
	pytest -q
lint:
	ruff check src tests && ruff format --check src tests
fmt:
	ruff check --fix src tests && ruff format src tests
migrate:
	alembic upgrade head
