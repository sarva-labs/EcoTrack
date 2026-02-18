# Contributing to EcoTrack

Thank you for your interest in contributing to EcoTrack! This guide will help you get started as a contributor to the Planetary Environmental Intelligence Platform.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [How to Contribute](#how-to-contribute)
- [Development Setup](#development-setup)
- [Code Style Guide](#code-style-guide)
- [Commit Message Conventions](#commit-message-conventions)
- [Pull Request Process](#pull-request-process)
- [Package Development Guide](#package-development-guide)
- [Testing Requirements](#testing-requirements)
- [Documentation Standards](#documentation-standards)
- [Release Process](#release-process)

---

## Code of Conduct

EcoTrack has adopted the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code. Please report unacceptable behavior to [conduct@ecotrack.earth](mailto:conduct@ecotrack.earth).

**Key principles:**
- Be respectful and inclusive
- Welcome newcomers and help them get started
- Focus on constructive feedback
- Prioritize the health of the community

---

## How to Contribute

### 🐛 Reporting Bugs

1. **Search existing issues** to avoid duplicates
2. **Use the bug report template** when creating a new issue
3. Include:
   - Clear title and description
   - Steps to reproduce
   - Expected vs actual behavior
   - Environment details (OS, Python version, Docker version)
   - Relevant logs or screenshots

### 💡 Suggesting Features

1. **Open a discussion** in the Ideas category first
2. Describe the use case and motivation
3. If there's consensus, create a formal issue with the feature request template

### 📝 Improving Documentation

Documentation improvements are always welcome! See [Documentation Standards](#documentation-standards) for guidelines.

### 🔧 Submitting Code

1. **Find or create an issue** describing what you want to work on
2. **Comment on the issue** to indicate you're working on it
3. **Fork** the repository and create a feature branch
4. **Implement** your changes following the code style guide
5. **Write tests** for new functionality
6. **Submit a Pull Request** following the PR process below

---

## Development Setup

### Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| Python | 3.11+ | ML packages, API, CLI |
| Node.js | 20+ | Dashboard, NestJS API |
| Docker | 24+ | Infrastructure services |
| Docker Compose | v2 | Local development stack |
| Git | 2.30+ | Version control |

### Step-by-Step Setup

```bash
# 1. Fork and clone
git clone https://github.com/<your-username>/ecotrack.git
cd ecotrack
git remote add upstream https://github.com/ecotrack/ecotrack.git

# 2. Create a virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# or: .venv\Scripts\activate  # Windows

# 3. Install all Python packages in editable mode
make install

# 4. Start infrastructure services
docker compose up -d postgres redis neo4j minio mlflow

# 5. Run database migrations
make migrate

# 6. Verify everything works
make test

# 7. (Optional) Install Node.js dependencies for frontend
npm install
```

### Environment Variables

Copy the development template and customize as needed:

```bash
cp configs/development/.env.example .env
```

Key variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `ECOTRACK_ENV` | `development` | Environment name |
| `DB_HOST` | `localhost` | PostgreSQL host |
| `DB_PORT` | `5432` | PostgreSQL port |
| `DB_NAME` | `ecotrack` | Database name |
| `REDIS_HOST` | `localhost` | Redis host |
| `S3_ENDPOINT` | `http://localhost:9000` | MinIO endpoint |
| `ML_MLFLOW_TRACKING_URI` | `http://localhost:5000` | MLflow tracking server |

---

## Code Style Guide

### Python (packages/, apps/api-python/, apps/worker/, apps/cli/)

We use **[Ruff](https://github.com/astral-sh/ruff)** for linting and formatting, and **[mypy](https://mypy-lang.org/)** for type checking.

**Configuration** (from [`pyproject.toml`](pyproject.toml)):

```toml
[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "N", "UP", "B", "A", "SIM", "TCH"]

[tool.mypy]
python_version = "3.11"
strict = true
```

**Key rules:**
- Line length: 100 characters maximum
- All functions must have type annotations
- Use `from __future__ import annotations` for forward references
- Prefer `dataclass` or `pydantic.BaseModel` over plain dicts
- Use `pathlib.Path` instead of string paths
- Async functions should use `async`/`await` (not threads)

**Running checks:**

```bash
# Lint
ruff check packages/ apps/api-python/ apps/worker/ apps/cli/

# Format
ruff format packages/ apps/api-python/ apps/worker/ apps/cli/

# Type check
mypy packages/ apps/api-python/ apps/worker/ apps/cli/
```

### TypeScript (apps/api/, apps/web/)

We use **ESLint** and **Prettier** for TypeScript code.

**Key rules:**
- Strict TypeScript (`strict: true`)
- Prefer `interface` over `type` for object shapes
- Use named exports
- React components use functional style with hooks

**Running checks:**

```bash
npx eslint apps/api/src apps/web/src
npx prettier --check "apps/**/*.{ts,tsx}"
```

### Naming Conventions

| Item | Convention | Example |
|------|-----------|---------|
| Python packages | `ecotrack_{name}` | `ecotrack_data` |
| Python modules | `snake_case.py` | `climate_forecaster.py` |
| Python classes | `PascalCase` | `ClimateForecaster` |
| Python functions | `snake_case` | `run_inference()` |
| TypeScript packages | `@ecotrack/{name}` | `@ecotrack/ui` |
| TypeScript files | `kebab-case.ts` | `climate-service.ts` |
| Docker images | `ecotrack/{service}` | `ecotrack/api` |
| Database schemas | `eco_{domain}` | `eco_climate` |
| Test files | `test_{module}.py` | `test_climate_forecaster.py` |

---

## Commit Message Conventions

We follow [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/) for clear, parseable commit history.

### Format

```
<type>(<scope>): <description>

[optional body]

[optional footer(s)]
```

### Types

| Type | Description | Example |
|------|-------------|---------|
| `feat` | New feature | `feat(ml): add crop yield predictor model` |
| `fix` | Bug fix | `fix(pipeline): handle empty API responses from NOAA` |
| `docs` | Documentation | `docs: update API.md with new endpoints` |
| `style` | Formatting | `style: apply ruff formatting to agents package` |
| `refactor` | Code refactoring | `refactor(kg): simplify Cypher query builder` |
| `perf` | Performance | `perf(inference): enable ONNX graph optimizations` |
| `test` | Tests | `test(causal): add counterfactual estimation tests` |
| `build` | Build system | `build: update PyTorch to 2.3` |
| `ci` | CI/CD | `ci: add integration test stage to pipeline` |
| `chore` | Maintenance | `chore: clean up unused imports` |

### Scopes

Use the package or app name as scope: `ml`, `data`, `geo`, `kg`, `agents`, `causal`, `rl`, `federated`, `api`, `web`, `worker`, `cli`, `infra`, `ci`.

### Examples

```bash
# Feature
git commit -m "feat(agents): add biodiversity specialist agent with habitat analysis tools"

# Bug fix
git commit -m "fix(pipeline): correctly handle CRS transformation for polar projections

The rasterio CRS transform was failing for EPSG:3413 (NSIDC Polar Stereographic).
Added explicit handling for polar coordinate systems.

Fixes #142"

# Breaking change
git commit -m "feat(api)!: rename /ml/v1/predict to /ml/v1/inference

BREAKING CHANGE: All ML prediction endpoints have been renamed from
/predict/* to /inference/* for consistency."
```

---

## Pull Request Process

### Before Submitting

1. **Sync with upstream:**
   ```bash
   git fetch upstream
   git rebase upstream/main
   ```

2. **Run all checks:**
   ```bash
   make lint
   make test
   ```

3. **Update documentation** if your change affects public APIs or behavior

### PR Requirements

- [ ] Clear title following commit conventions (e.g., `feat(ml): add species detector model`)
- [ ] Description explaining **what** and **why**
- [ ] Link to related issue(s)
- [ ] All CI checks pass (lint, type-check, tests)
- [ ] New features have tests
- [ ] Documentation updated if needed
- [ ] No unrelated changes

### Review Process

1. **Automated checks** run on every PR (lint, tests, security scan)
2. **One maintainer review** is required for merge
3. **Two maintainer reviews** for changes touching security, infrastructure, or core interfaces
4. Reviewers may request changes — address all comments before re-requesting review
5. PRs are merged via **squash merge** to keep history clean

### Review Guidelines for Reviewers

- Be constructive and kind
- Explain the **why** behind suggestions
- Distinguish between blocking issues and optional improvements
- Use GitHub suggestion blocks for small fixes
- Approve promptly once concerns are addressed

---

## Package Development Guide

### Adding a New Data Source

1. **Create a source module** in [`packages/data-pipeline/ecotrack_data/sources/`](packages/data-pipeline/ecotrack_data/sources/):

```python
# packages/data-pipeline/ecotrack_data/sources/my_source.py
from ecotrack_data.sources.base import DataSource, DataSourceConfig

class MySourceConfig(DataSourceConfig):
    """Configuration for MySource connector."""
    api_key: str
    base_url: str = "https://api.mysource.org/v1"
    rate_limit_rpm: int = 60

class MySource(DataSource):
    """Connector for MySource environmental data."""

    def __init__(self, config: MySourceConfig) -> None:
        super().__init__(config)
        self.config = config

    async def fetch(self, query: dict) -> list[dict]:
        """Fetch data from MySource API."""
        # Implement API calls here
        ...

    async def validate(self, data: list[dict]) -> list[dict]:
        """Validate and clean fetched data."""
        ...
```

2. **Register** in [`packages/data-pipeline/ecotrack_data/sources/__init__.py`](packages/data-pipeline/ecotrack_data/sources/__init__.py)

3. **Write tests** in `tests/unit/test_data_pipeline/test_my_source.py`

4. **Document** the source in [API.md](API.md) and this README

> 📖 Full tutorial: [Data Ingestion Guide](docs/tutorials/DATA_INGESTION.md)

### Adding a New ML Model

1. **Create a model module** in [`packages/ml/ecotrack_ml/models/`](packages/ml/ecotrack_ml/models/):

```python
# packages/ml/ecotrack_ml/models/my_model.py
import torch
from ecotrack_ml.models.base import EcoTrackModel

class MyModel(EcoTrackModel):
    """Description of what this model does."""

    def __init__(self, config: dict) -> None:
        super().__init__(config)
        # Build architecture
        ...

    def forward(self, batch: dict[str, torch.Tensor]) -> dict[str, torch.Tensor]:
        ...

    def compute_loss(self, preds, targets) -> torch.Tensor:
        ...

    def predict(self, inputs: dict[str, torch.Tensor]) -> dict[str, torch.Tensor]:
        ...
```

2. **Register** in [`packages/ml/ecotrack_ml/models/__init__.py`](packages/ml/ecotrack_ml/models/__init__.py)

3. **Write tests** in `tests/unit/test_ml/test_my_model.py`

> 📖 Full tutorial: [Model Training Guide](docs/tutorials/MODEL_TRAINING.md)

### Adding a New Agent

1. **Create a specialist** in [`packages/agents/ecotrack_agents/specialists.py`](packages/agents/ecotrack_agents/specialists.py) or a new module

2. **Add tools** in [`packages/agents/ecotrack_agents/tools/`](packages/agents/ecotrack_agents/tools/)

3. **Register** with the orchestrator in [`packages/agents/ecotrack_agents/orchestrator.py`](packages/agents/ecotrack_agents/orchestrator.py)

> 📖 Full tutorial: [Agent Development Guide](docs/tutorials/AGENT_DEVELOPMENT.md)

---

## Testing Requirements

### Coverage Targets

| Package | Minimum Coverage |
|---------|-----------------|
| `ecotrack_data` | 80% |
| `ecotrack_ml` | 75% |
| `ecotrack_agents` | 75% |
| `ecotrack_causal` | 80% |
| `ecotrack_rl` | 75% |
| `ecotrack_federated` | 75% |
| `ecotrack_kg` | 75% |
| `ecotrack_geo` | 80% |
| API endpoints | 85% |

### Test Types

- **Unit tests**: Test individual functions and classes in isolation. Mock external dependencies.
- **Integration tests**: Test interactions between packages or with real services (use Docker).
- **End-to-end tests**: Test complete user flows through the API.

### Writing Good Tests

```python
# tests/unit/test_ml/test_climate_forecaster.py
import pytest
import torch
from ecotrack_ml.models.climate_forecaster import ClimateForecaster

class TestClimateForecaster:
    """Tests for the Climate Forecaster model."""

    @pytest.fixture
    def model(self):
        """Create a model instance for testing."""
        config = {"input_channels": 5, "forecast_horizon": 14}
        return ClimateForecaster(config)

    @pytest.fixture
    def sample_batch(self):
        """Create a sample input batch."""
        return {
            "features": torch.randn(4, 30, 5),  # batch, time, channels
            "targets": torch.randn(4, 14, 1),    # batch, horizon, channels
        }

    def test_forward_shape(self, model, sample_batch):
        """Model output has correct shape."""
        output = model(sample_batch)
        assert output["predictions"].shape == (4, 14, 1)

    def test_loss_is_scalar(self, model, sample_batch):
        """Loss computation returns a scalar tensor."""
        output = model(sample_batch)
        loss = model.compute_loss(output, sample_batch)
        assert loss.dim() == 0

    def test_predict_returns_uncertainty(self, model, sample_batch):
        """Predict method returns uncertainty estimates."""
        result = model.predict(sample_batch)
        assert "predictions_std" in result
```

### Running Tests

```bash
# All tests
make test

# Specific package
pytest tests/unit/test_ml/ -v

# With coverage
pytest --cov=packages --cov-report=html --cov-report=term-missing

# Only fast tests (skip integration)
pytest -m "not integration" -v
```

---

## Documentation Standards

### File Naming

| Document Type | Location | Naming |
|--------------|----------|--------|
| Package README | `packages/{name}/README.md` | `README.md` |
| Tutorials | `docs/tutorials/` | `UPPER_SNAKE_CASE.md` |
| Architecture | `docs/architecture/` | `UPPER_SNAKE_CASE.md` |
| API reference | Root | `API.md` |

### Markdown Style

- Use ATX-style headers (`#`, `##`, `###`)
- Include a table of contents for documents over 100 lines
- Use fenced code blocks with language identifiers
- Use relative links for internal references
- Include Mermaid diagrams for architecture and flow descriptions
- Use tables for structured data
- Add alt text to images

### Docstrings (Python)

Use Google-style docstrings:

```python
def predict_yield(
    region_id: str,
    crop_type: str,
    season: str,
) -> YieldPrediction:
    """Predict crop yield for a region.

    Uses satellite-derived vegetation indices combined with weather
    data to estimate expected yield in tonnes per hectare.

    Args:
        region_id: H3 cell identifier at resolution 7.
        crop_type: Crop identifier (e.g., "wheat", "maize", "rice").
        season: Growing season identifier (e.g., "2026-spring").

    Returns:
        YieldPrediction with mean, confidence interval, and contributing factors.

    Raises:
        ValueError: If crop_type is not supported.
        DataNotFoundError: If no data exists for the specified region.

    Example:
        >>> result = predict_yield("872830828ffffff", "wheat", "2026-spring")
        >>> print(f"Expected yield: {result.mean_tonnes_ha:.1f} t/ha")
    """
```

---

## Release Process

EcoTrack follows [Semantic Versioning](https://semver.org/):

- **MAJOR** (`x.0.0`): Breaking API changes
- **MINOR** (`0.x.0`): New features, backward-compatible
- **PATCH** (`0.0.x`): Bug fixes, backward-compatible

### Release Steps

1. **Create a release branch**: `git checkout -b release/v1.2.0`
2. **Update version** in [`pyproject.toml`](pyproject.toml) and [`package.json`](package.json)
3. **Update [CHANGELOG.md](CHANGELOG.md)** with all changes since last release
4. **Run full test suite**: `make lint && make test`
5. **Create PR** to `main` branch
6. After merge, **tag the release**: `git tag v1.2.0`
7. **Push tag**: `git push origin v1.2.0`
8. GitHub Actions will automatically build and publish Docker images

---

## Questions?

- **General questions**: Open a [Discussion](https://github.com/ecotrack/ecotrack/discussions)
- **Bug reports**: Open an [Issue](https://github.com/ecotrack/ecotrack/issues/new?template=bug_report.md)
- **Feature requests**: Open a [Discussion](https://github.com/ecotrack/ecotrack/discussions/categories/ideas) first
- **Security issues**: See [SECURITY.md](SECURITY.md) for responsible disclosure

---

Thank you for helping build tools to understand and protect our planet! 🌍
