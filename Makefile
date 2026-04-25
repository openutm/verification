.PHONY: help install run verify test coverage lint format clean gui gui-stop dev-backend dev-frontend allure-report allure-serve allure-open

help:
	@echo "  make help		Show this help message"
	@echo "  make install		Install dependencies"
	@echo "  make run		Run the verification tool locally"
	@echo "  make verify		Run the verification tool (alias for run)"
	@echo "  make test		Run pytest for the project"
	@echo "  make coverage		Run pytest with coverage report"
	@echo "  make lint		Run linters and type checker"
	@echo "  make format		Format the codebase"
	@echo "  make clean		Clean up build artifacts and cache"
	@echo "  make gui		Run GUI mode in Docker (single image)"
	@echo "  make gui-stop		Stop the GUI Docker container"
	@echo "  make dev-backend	Run the backend locally with hot-reload (uvicorn)"
	@echo "  make dev-frontend	Run the Vite dev server locally"

install:
	uv sync --dev -U

run:
	./verify.sh

verify: run

test:
	uv run pytest tests/

lint:
	uv run ruff check src/openutm_verification/ tests/
	uv run pylint src/openutm_verification/
	uv run mypy src/openutm_verification/

format:
	uv run ruff format .
	uv run ruff check --select "I" --fix

coverage:
	uv run pytest --cov=src/openutm_verification --cov-report=term-missing --cov-report=html tests/

# GUI Mode (Docker, single image: backend serves the built frontend)
gui:
	DOCKER_BUILDKIT=1 docker compose up --build -d

gui-stop:
	docker compose down

# Local development: run these in two terminals (no Docker required)
dev-backend:
	uv run uvicorn openutm_verification.server.main:app --reload --port 8989

dev-frontend:
	cd web-editor && npm install && npm run dev

# Allure Reporting (requires npx allure — uses Allure 3 "awesome" theme)
allure-report:
	npx allure awesome reports/allure-results --output reports/allure-report

allure-serve:
	npx allure awesome reports/allure-results --output reports/allure-report
	npx allure open reports/allure-report

allure-open:
	npx allure open reports/allure-report

clean:
	rm -rf __pycache__
	rm -rf .pytest_cache
	rm -rf .mypy_cache
	rm -rf .ruff_cache
	rm -rf htmlcov
	rm -rf reports/*
	rm -f .coverage
	rm -f lcov.info
	find . -name "*.pyc" -delete
	find . -name "__pycache__" -delete
