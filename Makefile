.PHONY: install dev up adapty-login test test-docker demo-events demo demo-reset lint fmt migrate offline-data board impact

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
	rm -rf /tmp/seed-data && git clone --depth 1 https://github.com/kpotehin/adapty-seed-data-hack.git /tmp/seed-data && mkdir -p data/offline && cp /tmp/seed-data/data/offline/*.csv.gz data/offline/ && cp /tmp/seed-data/data/lumen_dataset.json.gz data/

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

# One command before a demo: api up (migrations run), seed data present, 1000 demo users loaded.
demo:
	docker compose up -d --build api
	@for i in $$(seq 60); do curl -sf localhost:8000/v1/health >/dev/null && break; sleep 1; done
	@curl -sf localhost:8000/v1/health >/dev/null || (echo "api did not start: docker compose logs api" && exit 1)
	@test -f data/lumen_dataset.json.gz || $(MAKE) offline-data
	$(MAKE) demo-events
	@echo "API docs: http://localhost:8000/docs  ·  web: cd web && npm run dev → http://localhost:5173  ·  script: docs/demo.md"

# Clean slate: stop the api, delete the local database, run `make demo` again.
demo-reset:
	docker compose down
	rm -f data/app.db data/app.db-wal data/app.db-shm
	$(MAKE) demo
