.PHONY: install dev up adapty-login test test-docker demo-events lint fmt migrate offline-data board impact

install:
	python3 -m venv .venv && . .venv/bin/activate && pip install -U pip && pip install -e ".[dev]"

dev:
	. .venv/bin/activate && uvicorn feature_signal.main:app --reload --port 8000

test:
	. .venv/bin/activate && pytest -q

lint:
	. .venv/bin/activate && ruff check .

fmt:
	. .venv/bin/activate && ruff format . && ruff check --fix .

migrate:
	. .venv/bin/activate && alembic upgrade head

offline-data:
	git clone --depth 1 https://github.com/kpotehin/adapty-seed-data-hack.git /tmp/seed-data && mkdir -p data/offline && cp /tmp/seed-data/data/offline/*.csv.gz data/offline/ && cp /tmp/seed-data/data/lumen_dataset.json.gz data/

# Docker: the backend image with the Adapty CLI (see docker-compose.yml).
up:
	docker compose up --build api

adapty-login:
	docker compose run --rm adapty-login

# No python3-venv on the host? Run the suite in a clean container (same as CI would).
test-docker:
	docker compose run --rm --build test

# Task graph (docs/tasks): `make board ROLE=A`, `make impact` (what your branch affects).
board:
	python3 tools/tasks.py board $(if $(ROLE),--role $(ROLE))

impact:
	python3 tools/tasks.py impact --diff origin/main

# Synthetic demo events for the first 1000 Lumen seed users (needs `make offline-data` and a running api).
demo-events:
	docker compose exec api python scripts/load_demo_events.py --base http://localhost:8000 --users 1000
