.PHONY: help up down logs build rebuild test test-unit test-integration seed demo-happy clean lint format check install dev ensure-env normalize-env

# Choose compose command (docker-compose v1 or docker compose v2)
COMPOSE := $(shell if command -v docker-compose >/dev/null 2>&1; then echo docker-compose; else echo docker compose; fi)
ENV_FILE := .env
ENV_TEMPLATE := .env.example
DEFAULT_STOCK_LOCATIONS := ["Stock","WH/Stock"]
FULL_COMPOSE_FILE := docker/docker-compose.full.yml
FULL_STACK_MODULES := base,mrp,stock

# Default target
help: ## Show this help message
	@echo "HERMES Odoo Adapter - Development Commands"
	@echo "========================================"
	@awk 'BEGIN {FS = ":.*##"} /^[a-zA-Z_-]+:.*##/ {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

# Docker Management

ensure-env: ## Create .env from template if missing
	@if [ ! -f $(ENV_FILE) ]; then \
		cp $(ENV_TEMPLATE) $(ENV_FILE); \
		echo "Created $(ENV_FILE) from template"; \
	else \
		echo "Using existing $(ENV_FILE)"; \
	fi

normalize-env: ## Ensure .env uses the expected JSON formats
	@if [ -f $(ENV_FILE) ]; then \
		python3 scripts/normalize_env.py $(ENV_FILE) '$(DEFAULT_STOCK_LOCATIONS)'; \
	else \
		echo "$(ENV_FILE) not found, run 'make ensure-env' first"; \
	fi

up: ## Start all services in background
	$(MAKE) ensure-env normalize-env
	$(COMPOSE) -f docker/docker-compose.demo.yml up -d --build
	@echo "Services starting... Check status with 'make logs'"

down: ## Stop all services
	$(COMPOSE) -f docker/docker-compose.demo.yml down

logs: ## Follow logs from all services
	$(COMPOSE) -f docker/docker-compose.demo.yml logs -f

logs-adapter: ## Follow logs from adapter service only
	$(COMPOSE) -f docker/docker-compose.demo.yml logs -f adapter

build: ## Build all Docker images
	$(COMPOSE) -f docker/docker-compose.demo.yml build

rebuild: ## Rebuild and restart services
	$(COMPOSE) -f docker/docker-compose.demo.yml build --no-cache
	$(COMPOSE) -f docker/docker-compose.demo.yml up -d

# Full stack with real Odoo
up-full: ## Start full stack with real Odoo ERP (auto-initializes base modules on first run)
	$(MAKE) ensure-env normalize-env
	@echo "Ensuring PostgreSQL is running..."
	$(COMPOSE) -f $(FULL_COMPOSE_FILE) up -d postgres
	@echo "Waiting for PostgreSQL to become ready..."
	$(COMPOSE) -f $(FULL_COMPOSE_FILE) exec -T postgres sh -c "until pg_isready -U odoo -d odoo >/dev/null 2>&1; do sleep 1; done"
	@if ! $(COMPOSE) -f $(FULL_COMPOSE_FILE) exec -T postgres psql -U odoo -d odoo -tAc "SELECT 1 FROM information_schema.tables WHERE table_name='ir_module_module';" | grep -q 1; then \
		echo "Initializing Odoo database modules ($(FULL_STACK_MODULES))..."; \
		$(COMPOSE) -f $(FULL_COMPOSE_FILE) run --rm odoo odoo -c /etc/odoo/odoo.conf -i $(FULL_STACK_MODULES) --without-demo=False --stop-after-init; \
	else \
		echo "Odoo database already initialized. Skipping module install."; \
	fi
	$(COMPOSE) -f $(FULL_COMPOSE_FILE) up -d
	@echo "🏭 Full HERMES stack with real Odoo starting..."
	@echo "This includes: Postgres, Odoo, Orion-LD, MongoDB, and Adapter"
	@echo "Odoo base modules verified; subsequent startups reuse the existing database."

up-monitoring: ## Start full stack with monitoring (Grafana + Prometheus)
	$(MAKE) ensure-env
	$(COMPOSE) -f $(FULL_COMPOSE_FILE) --profile monitoring up -d
	@echo "📊 Full stack with monitoring started"
	@echo "Grafana: http://localhost:3000 (admin/admin)"
	@echo "Prometheus: http://localhost:9090"

logs-full: ## Follow logs from full stack
	$(COMPOSE) -f $(FULL_COMPOSE_FILE) logs -f

logs-odoo: ## Follow logs from real Odoo
	$(COMPOSE) -f $(FULL_COMPOSE_FILE) logs -f odoo

down-full: ## Stop full stack
	$(COMPOSE) -f $(FULL_COMPOSE_FILE) down

# Development
install: ## Install Python dependencies with Poetry
	poetry install

dev: ## Start development server locally
	poetry run python -m hermes_odoo_adapter.main

# Testing
test: ## Run all tests
	poetry run pytest tests/ -v --cov=hermes_odoo_adapter --cov-report=term-missing

test-unit: ## Run unit tests only
	poetry run pytest tests/unit/ -v

test-integration: ## Run integration tests (requires Docker stack)
	@echo "Starting test stack..."
	$(MAKE) ensure-env
	$(COMPOSE) -f docker/docker-compose.demo.yml up -d
	@echo "Waiting for services to be ready..."
	sleep 10
	poetry run pytest tests/integration/ -v
	@echo "Stopping test stack..."
	$(COMPOSE) -f docker/docker-compose.demo.yml down

test-docker: ## Run tests inside Docker container
	$(MAKE) ensure-env
	$(COMPOSE) -f docker/docker-compose.demo.yml exec adapter pytest tests/ -v

# Code Quality
lint: ## Run linting with ruff
	poetry run ruff check src/ tests/

format: ## Format code with black and ruff
	poetry run black src/ tests/
	poetry run ruff --fix src/ tests/

check: ## Run all code quality checks
	poetry run ruff check src/ tests/
	poetry run black --check src/ tests/
	poetry run mypy src/

# Data Management
seed: ## Seed demo data into Orion-LD and Odoo Mock
	@echo "Seeding demo data..."
	poetry run python scripts/seed_orion_demo.py
	poetry run python scripts/seed_odoo_demo.py
	@echo "Demo data seeded successfully!"

seed-real-odoo: ## Seed real Odoo ERP with demo manufacturing data
	@echo "Seeding real Odoo ERP..."
	poetry run python scripts/seed_real_odoo.py
	@echo "Real Odoo seeded successfully!"

seed-full: ## Seed both real Odoo and Orion-LD for full stack demo
	@echo "Seeding full stack demo data..."
	poetry run python scripts/seed_real_odoo.py
	poetry run python scripts/seed_orion_demo.py
	@echo "Full stack demo data seeded successfully!"

# Demo Scenarios
demo-happy: ## Run happy path demo scenario
	@echo "Running happy path demo..."
	curl -X POST http://localhost:8080/admin/recompute/P123 \
		-H 'Content-Type: application/json' \
		-d '{"projectCode": "CTRL-PANEL-A1", "station": "S2"}'
	@echo "\nDemo completed! Check Orion-LD entities:"
	@echo "curl 'http://localhost:1026/ngsi-ld/v1/entities?type=Reservation'"

demo-shortage: ## Run shortage scenario
	@echo "Creating shortage scenario..."
	curl -X POST http://localhost:8069/debug/stock/5 \
		-H 'Content-Type: application/json' \
		-d '0.0'
	@echo "Running demo with shortage..."
	curl -X POST http://localhost:8080/admin/recompute/P124 \
		-H 'Content-Type: application/json' \
		-d '{"projectCode": "CTRL-PANEL-A1", "station": "S3"}'
	@echo "\nShortage demo completed! Check entities:"
	@echo "curl 'http://localhost:1026/ngsi-ld/v1/entities?type=Shortage'"

# Debugging
debug-products: ## Show all products in Odoo Mock
	curl -s http://localhost:8069/debug/products | jq

debug-boms: ## Show all BOMs in Odoo Mock
	curl -s http://localhost:8069/debug/boms | jq

debug-stock: ## Show all stock in Odoo Mock
	curl -s http://localhost:8069/debug/stock | jq

debug-orion: ## Show all entities in Orion-LD
	@echo "=== Projects ==="
	curl -s 'http://localhost:1026/ngsi-ld/v1/entities?type=Project' | jq
	@echo "\n=== Reservations ==="
	curl -s 'http://localhost:1026/ngsi-ld/v1/entities?type=Reservation' | jq
	@echo "\n=== Shortages ==="
	curl -s 'http://localhost:1026/ngsi-ld/v1/entities?type=Shortage' | jq

# Health Checks
health: ## Check health of all services
	@echo "=== Service Health Checks ==="
	@echo "Adapter:"
	@curl -s http://localhost:8080/healthz | jq || echo "❌ Adapter not responding"
	@echo "Odoo Mock:"
	@curl -s http://localhost:8069/healthz | jq || echo "❌ Odoo Mock not responding"
	@echo "Orion-LD:"
	@curl -s http://localhost:1026/version | jq || echo "❌ Orion-LD not responding"

ready: ## Check readiness of adapter
	curl -s http://localhost:8080/readyz | jq

metrics: ## Show adapter metrics
	curl -s http://localhost:8080/metrics

# Cleanup
clean: ## Clean up containers, volumes, and images
	$(COMPOSE) -f docker/docker-compose.demo.yml down -v
	docker system prune -f

clean-all: ## Clean up everything including images
	$(COMPOSE) -f docker/docker-compose.demo.yml down -v --rmi all
	docker system prune -a -f

# Quick Start
quick-start: build up seed ## Build, start services, and seed data
	@echo "🚀 Quick start completed!"
	@echo "Services are starting up. Wait a moment, then try:"
	@echo "  make health     # Check service health"
	@echo "  make demo-happy # Run demo scenario"
	@echo "  make logs       # Watch logs"

# Development workflow
dev-setup: install build ## Complete development setup
	@echo "Development environment setup complete!"
	@echo "Run 'make up' to start services"

# CI/Testing workflow  
ci: install lint check test-unit ## Run CI pipeline locally
	@echo "✅ CI pipeline completed successfully!"

# Reset everything for fresh start
reset: clean install build up seed ## Reset and restart everything
	@echo "🔄 Complete reset completed!"
