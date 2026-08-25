.PHONY: install key run test lint migrate revision docker-up docker-down

install:
	python -m pip install -r requirements.txt -r requirements-dev.txt

key:
	python scripts/generate_key.py

run:
	python -m app.main

test:
	python -m unittest discover -s tests -v

lint:
	ruff check app tests scripts
	ruff format --check app tests scripts

migrate:
	alembic upgrade head

revision:
	alembic revision --autogenerate -m "schema update"

docker-up:
	docker compose up -d --build

docker-down:
	docker compose down
