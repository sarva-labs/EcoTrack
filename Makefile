.PHONY: install lint test format docker-up docker-down migrate

install:
	@echo "Installing Node.js dependencies..."
	npm install
	@echo "Installing Python dependencies..."
	pip install -e packages/core[dev]
	pip install -e packages/data-pipeline
	pip install -e packages/ml
	pip install -e packages/geo
	pip install -e packages/knowledge-graph
	pip install -e packages/agents
	pip install -e packages/causal
	pip install -e packages/rl-policy
	pip install -e packages/federated
	pip install -e apps/api-python
	pip install -e apps/worker
	pip install -e apps/cli

lint:
	@echo "Running ruff..."
	ruff check packages/ apps/api-python/ apps/worker/ apps/cli/
	@echo "Running mypy..."
	mypy packages/ apps/api-python/ apps/worker/ apps/cli/

test:
	@echo "Running pytest..."
	pytest -v --tb=short

format:
	@echo "Formatting with ruff..."
	ruff format packages/ apps/api-python/ apps/worker/ apps/cli/
	ruff check --fix packages/ apps/api-python/ apps/worker/ apps/cli/

docker-up:
	docker compose up -d

docker-down:
	docker compose down

migrate:
	@echo "Running database migrations..."
	alembic upgrade head

clean:
	@echo "Cleaning build artifacts..."
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name *.egg-info -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
