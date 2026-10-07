# Korinnia — developer & operator commands. Run `make help` for the list.
SHELL := /bin/bash
.DEFAULT_GOAL := help

-include .env

COMPOSE      ?= docker compose
COMPOSE_PROD ?= docker compose -f docker-compose.yml
PROJECT      ?= korinnia
TEST_DB      ?= korinnia_test
PLAYWRIGHT_IMAGE ?= mcr.microsoft.com/playwright:v1.63.0-noble
E2E_PORT     ?= 8091

.PHONY: help
help: ## Show this help
	@grep -hE '^[a-zA-Z0-9_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

.env:
	cp .env.example .env
	@echo ">> created .env from .env.example — review it before production use"

# --- Stack ------------------------------------------------------------------------------
.PHONY: up
up: .env ## Build and start the dev stack (hot reload); migrations run automatically
	$(COMPOSE) up -d --build --wait
	@echo ""
	@echo "  App:       http://localhost:$(or $(HTTP_PORT),8080)"
	@echo "  API docs:  http://localhost:$(or $(HTTP_PORT),8080)/api/docs"
	@echo "  Vite:      http://localhost:5173  (direct, also proxied by nginx)"

.PHONY: up-prod
up-prod: .env ## Start the production stack (no dev overrides)
	$(COMPOSE_PROD) up -d --build --wait

.PHONY: down
down: ## Stop the stack (data volumes are kept)
	$(COMPOSE) down

.PHONY: ps
ps: ## Show service status
	$(COMPOSE) ps

.PHONY: logs
logs: ## Follow logs (make logs s=backend for one service)
	$(COMPOSE) logs -f --tail=200 $(s)

.PHONY: build
build: .env ## Build all images
	$(COMPOSE) build

# --- Database ---------------------------------------------------------------------------
.PHONY: migrate
migrate: ## Apply database migrations
	$(COMPOSE) exec backend alembic upgrade head

.PHONY: revision
revision: ## Autogenerate a migration: make revision m="add person table"
	@test -n "$(m)" || (echo 'usage: make revision m="message"' && exit 1)
	$(COMPOSE) exec backend alembic revision --autogenerate -m "$(m)"

.PHONY: psql
psql: ## Open psql in the database
	$(COMPOSE) exec postgres sh -c 'psql -U $$POSTGRES_USER -d $$POSTGRES_DB'

.PHONY: seed
seed: ## Give every user their own demo family (25 people, 5 generations)
	$(COMPOSE) exec backend python -m app.seed --all-users

# --- Quality ----------------------------------------------------------------------------
.PHONY: test
test: test-backend test-frontend ## Run backend and frontend tests

.PHONY: test-db
test-db:
	@$(COMPOSE) up -d --wait postgres
	@$(COMPOSE) exec -T postgres sh -c \
	  'psql -U $$POSTGRES_USER -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='"'"'$(TEST_DB)'"'"'" | grep -q 1 \
	   || createdb -U $$POSTGRES_USER $(TEST_DB)'

.PHONY: test-backend
test-backend: .env test-db ## Backend tests with coverage (uses a separate test database)
	$(COMPOSE) run --rm --no-deps -e POSTGRES_DB=$(TEST_DB) backend \
	  pytest --cov=app --cov-report=term-missing $(args)

.PHONY: test-frontend
test-frontend: .env ## Frontend unit tests (Vitest)
	$(COMPOSE) run --rm --no-deps frontend sh -c "npm ci --no-audit --no-fund --loglevel=error && npm test"

# Test accounts do not need their own demo family; the admin gets one from app.seed.
.PHONY: test-e2e
test-e2e: .env ## End-to-end tests (Playwright) on a throwaway production-build stack
	@set -e; \
	E2E="docker compose -p $(PROJECT)-e2e -f docker-compose.yml"; \
	HTTP_PORT=$(E2E_PORT) ENVIRONMENT=production DEMO_TREE_FOR_NEW_USERS=false \
	  $$E2E up -d --build --wait; \
	$$E2E exec -T backend python -m app.seed; \
	status=0; \
	docker run --rm --network $(PROJECT)-e2e_default -e E2E_BASE_URL=http://nginx -e CI=$(CI) \
	  -v "$(CURDIR)/frontend:/app" -v $(PROJECT)-e2e-node-modules:/app/node_modules -w /app \
	  $(PLAYWRIGHT_IMAGE) sh -c "npm ci --no-audit --no-fund --loglevel=error && npx playwright test $(args)" \
	  || status=$$?; \
	$$E2E down -v --remove-orphans >/dev/null 2>&1; \
	exit $$status

.PHONY: lint
lint: .env ## Lint + format check + type check (backend & frontend)
	$(COMPOSE) run --rm --no-deps backend sh -c "ruff check . && ruff format --check . && mypy ."
	$(COMPOSE) run --rm --no-deps frontend sh -c \
	  "npm ci --no-audit --no-fund --loglevel=error && npm run lint && npm run format:check && npm run typecheck"

.PHONY: fmt
fmt: .env ## Auto-format backend and frontend code
	$(COMPOSE) run --rm --no-deps backend sh -c "ruff check --fix . && ruff format ."
	$(COMPOSE) run --rm --no-deps frontend npm run format

# --- Data safety ------------------------------------------------------------------------
.PHONY: backup
backup: ## Back up database + media to ./backups/<timestamp>/
	deploy/scripts/backup.sh

.PHONY: restore
restore: ## Restore from a backup: make restore dir=backups/<timestamp>
	@test -n "$(dir)" || (echo 'usage: make restore dir=backups/<timestamp>' && exit 1)
	deploy/scripts/restore.sh "$(dir)"

.PHONY: export
export: ## Family archive export (available in the final phase)
	@echo "Family archive export is implemented in the final phase (11)."
