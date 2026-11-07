.PHONY: install dev test test-docker lint fmt migrate offline-data

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
	git clone --depth 1 https://github.com/kpotehin/adapty-seed-data-hack.git /tmp/seed-data && mkdir -p data/offline && cp /tmp/seed-data/data/offline/*.csv.gz data/offline/

# No python3-venv on the host? Run the suite in a clean container (same as CI would).
test-docker:
	docker run --rm --user $$(id -u):$$(id -g) -e HOME=/tmp -v "$$PWD":/app -w /app python:3.12-slim \
	  sh -c "pip install -q --user -e '.[dev]' && python -m pytest -q && python -m ruff check ."
