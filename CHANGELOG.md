# Changelog

All notable changes to EcoTrack will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Planned
- Apache Kafka event streaming integration
- Apache Airflow DAG orchestration
- GraphQL API layer
- ONNX model optimization pipeline

---

## [0.1.0] - 2026-02-18

### Added

#### Platform Core
- Initial release of the EcoTrack Planetary Environmental Intelligence Platform
- Core domain models for 5 environmental domains: climate, biodiversity, health, food security, resource equity
- Configuration management with environment-based YAML configs
- Structured logging with correlation IDs and domain context
- Prometheus metrics integration for all services
- Security module with JWT/API key authentication, rate limiting, and input sanitization

#### Data Pipeline (`ecotrack_data`)
- Extensible `DataSource` base class for building connectors
- 7 real-world data source connectors:
  - **Copernicus** — Sentinel satellite imagery via SciHub API
  - **NASA Earthdata** — MODIS, Landsat, VIIRS products
  - **NOAA Climate** — Station observations and GFS forecasts
  - **OpenAQ** — Real-time air quality measurements from 100+ countries
  - **GBIF** — Species occurrence records from the Global Biodiversity Information Facility
  - **ERA5** — Climate reanalysis data (1940–present) from Copernicus CDS
  - **USDA CropScape** — Cropland data layers for the United States
- 3 data processor types: raster, tabular, and time-series
- Multi-backend storage: local filesystem, S3/MinIO, PostgreSQL
- Data source registry for dynamic connector management
- Pipeline orchestration framework

#### Machine Learning (`ecotrack_ml`)
- 5 model architectures:
  - **Climate Forecaster** — Temporal Convolutional Network + Transformer for multi-variate forecasting
  - **Land Cover Segmenter** — U-Net with ResNet encoder for semantic segmentation
  - **Species Detector** — CNN classifier (ResNet/EfficientNet) for species identification
  - **Anomaly Detector** — Variational Autoencoder for environmental anomaly detection
  - **Crop Yield Predictor** — Gradient-boosted ensemble for yield estimation
- PyTorch 2.x training pipeline with mixed precision, `torch.compile`, and cosine scheduling
- Evaluation framework with domain-specific metrics
- ONNX export and inference engine with graph optimization
- Weighted ensemble engine with uncertainty quantification
- Feature store backed by PostgreSQL + pgvector
- MLflow integration for experiment tracking and model registry

#### Geospatial (`ecotrack_geo`)
- CRS transformation utilities
- Raster processing (read, write, reproject, clip)
- H3 hexagonal tiling at configurable resolutions
- Vector geometry operations

#### Knowledge Graph (`ecotrack_kg`)
- Neo4j 5 client with connection pooling
- ENVO/SWEET environmental ontology builder
- Cypher query builder and template library
- Graph reasoning engine for causal and taxonomic queries

#### Multi-Agent System (`ecotrack_agents`)
- Base agent framework with tool-use capabilities
- 5 specialist agents: Climate, Biodiversity, Health, Food Security, Equity
- Orchestrator with hierarchical task decomposition and synthesis
- 16+ agent tools: data query, ML inference, geospatial analysis, visualization, knowledge graph
- Shared conversation memory

#### Causal Inference (`ecotrack_causal`)
- Causal discovery: Granger causality, PC algorithm
- Causal estimation: IPTW, propensity score matching, regression adjustment
- Counterfactual analysis for policy evaluation
- Environmental causal analysis toolkit

#### Reinforcement Learning (`ecotrack_rl`)
- 3 custom Gymnasium environments:
  - **Water Allocation** — Multi-stakeholder water resource optimization
  - **Carbon Trading** — Emissions trading market simulation
  - **Conservation Planning** — Protected area selection with budget constraints
- DQN agent with experience replay and target networks
- PPO agent with generalized advantage estimation
- Reward shaping utilities and policy evaluator

#### Federated Learning (`ecotrack_federated`)
- 4 aggregation strategies: FedAvg, FedProx, FedMedian, FedTrimmedMean
- Differential privacy with configurable epsilon/delta budgets
- Federated client and server framework
- Support for heterogeneous data distributions

#### FastAPI Python API
- 45+ REST endpoints organized by environmental domain
- Pydantic request/response schemas with validation
- JWT and API key authentication middleware
- Rate limiting (free/researcher/institutional tiers)
- Input sanitization and CSP headers
- Health check, metrics, and version endpoints
- Swagger/OpenAPI documentation at `/docs`

#### Next.js Dashboard
- Geospatial analytics dashboard with MapLibre GL and deck.gl
- Domain-specific pages: climate, biodiversity, health, food, equity
- Alert panel with real-time updates
- Metric cards and summary views
- Responsive layout with Tailwind CSS

#### CLI
- Click-based command-line interface
- Data ingestion commands
- Model training and evaluation commands

#### Celery Worker
- Async task processing for data ingestion and model training
- Redis broker with `data` and `ml` queues

#### Infrastructure
- Docker Compose development stack (PostgreSQL, Redis, Neo4j, MinIO, MLflow)
- Dockerfiles for API, worker, and web services
- Kubernetes manifests with Kustomize base and overlays (staging, production)
- HPA autoscaling, PodDisruptionBudgets, NGINX ingress
- Terraform modules for AWS: VPC, EKS, RDS, ElastiCache, S3, ECR
- Prometheus alerting rules and scrape configs
- Grafana dashboard for platform overview

#### Testing
- 60+ unit tests across all packages
- Integration test suite for pipeline flows
- pytest configuration with async support
- Shared test fixtures and conftest

#### Documentation
- System Architecture document with Mermaid diagrams
- Technical Vision document
- API reference documentation
- Contributing guide with code style and PR process
- Quickstart, data ingestion, model training, and agent development tutorials
- Research whitepaper
- Setup guide with troubleshooting

#### CI/CD
- GitHub Actions workflows for lint, test, build, and deploy
- Multi-stage Docker builds with layer caching
- Security scanning with Trivy

---

[Unreleased]: https://github.com/ecotrack/ecotrack/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/ecotrack/ecotrack/releases/tag/v0.1.0
