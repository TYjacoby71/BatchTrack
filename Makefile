
.PHONY: help install test lint format type-check docs-guard migrate upgrade downgrade clean

help:  ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install:  ## Install dependencies and setup pre-commit
	pip install -r requirements.txt
	pre-commit install

test:  ## Run all tests
	python -m pytest tests/ -v

test-watch:  ## Run tests in watch mode
	python -m pytest tests/ -v --tb=short -f

lint:  ## Run all linters
	ruff check app/ tests/
	black --check app/ tests/
	isort --check-only app/ tests/

format:  ## Format code
	black app/ tests/
	isort app/ tests/
	ruff --fix app/ tests/

type-check:  ## Run type checking
	mypy app/

docs-guard:  ## Enforce PR documentation schema
	python3 scripts/validate_pr_documentation.py

quality:  ## Run all quality checks
	$(MAKE) lint
	$(MAKE) type-check
	$(MAKE) docs-guard
	$(MAKE) test

migrate:  ## Generate new migration
	flask db migrate

upgrade:  ## Apply migrations
	flask db upgrade

downgrade:  ## Revert last migration
	flask db downgrade

clean:  ## Clean cache files
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +

# Database commands
db-reset:  ## Reset database (WARNING: destroys data)
	flask db downgrade base
	flask db upgrade
	flask init-production

# Development
dev:  ## Run development server
	python run.py

# CI commands
ci-test:  ## Run CI test suite
	$(MAKE) quality
