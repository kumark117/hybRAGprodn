PYTHON ?= python
NPM ?= npm

.PHONY: backend frontend test backend-test frontend-check lint docker-up docker-down eval index-folder

backend:
	cd backend && $(PYTHON) -m uvicorn app.main:app --reload --port 8000

frontend:
	cd frontend && $(NPM) run dev

backend-test:
	cd backend && $(PYTHON) -m pytest

frontend-check:
	cd frontend && $(NPM) run typecheck && $(NPM) test

test: backend-test frontend-check

lint:
	cd backend && $(PYTHON) -m ruff check app tests || true
	cd frontend && $(NPM) run lint || true

docker-up:
	docker compose up --build

docker-down:
	docker compose down

eval:
	cd backend && $(PYTHON) -m app.evaluation.run

index-folder:
	cd backend && $(PYTHON) -m app.cli index-folder "$(DIR)"
