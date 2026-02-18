# Quickstart: Getting Started with EcoTrack

Get EcoTrack running locally and make your first API calls in under 5 minutes.

---

## Prerequisites

| Tool | Version | Installation |
|------|---------|-------------|
| Docker | 24+ | [Get Docker](https://docs.docker.com/get-docker/) |
| Docker Compose | v2+ | Included with Docker Desktop |
| curl | Any | Pre-installed on macOS/Linux |

**System requirements**: 8 GB RAM minimum (16 GB recommended), 10 GB free disk space.

---

## Step 1: Clone the Repository

```bash
git clone https://github.com/ecotrack/ecotrack.git
cd ecotrack
```

---

## Step 2: Configure Environment

Copy the development environment template:

```bash
cp configs/development/.env.example .env
```

The defaults work for local development — no changes needed.

---

## Step 3: Start All Services

```bash
docker compose up -d
```

This launches:

| Service | Port | Description |
|---------|------|-------------|
| **PostgreSQL** | 5432 | Relational DB with PostGIS + TimescaleDB |
| **Redis** | 6379 | Cache and message broker |
| **Neo4j** | 7474 / 7687 | Knowledge graph database |
| **MinIO** | 9000 / 9001 | S3-compatible object storage |
| **MLflow** | 5000 | ML experiment tracking |
| **FastAPI** | 8000 | Python API (45+ endpoints) |
| **Next.js** | 3000 | Geospatial dashboard |
| **Celery Worker** | — | Async task processing |

Wait for all services to become healthy (about 30–60 seconds):

```bash
docker compose ps
```

All services should show `healthy` or `running` status.

---

## Step 4: Verify the API

```bash
curl http://localhost:8000/api/health
```

Expected response:

```json
{
  "status": "healthy",
  "version": "0.1.0",
  "service": "ecotrack-api"
}
```

---

## Step 5: Explore the Domains

List all available environmental domains:

```bash
curl http://localhost:8000/api/v1/domains
```

---

## Step 6: Make Your First Domain Queries

### Climate: Query Temperature Observations

```bash
curl "http://localhost:8000/api/v1/climate/observations?variable=temperature&page_size=3"
```

### Biodiversity: Search Endangered Species

```bash
curl "http://localhost:8000/api/v1/biodiversity/species?conservation_status=EN"
```

### Health: Check Air Quality

```bash
curl "http://localhost:8000/api/v1/health/air-quality?min_lat=28&max_lat=29&min_lon=77&max_lon=78"
```

### Food Security: View Drought Alerts

```bash
curl "http://localhost:8000/api/v1/food-security/drought-alerts?severity=D3"
```

### Resources: Water Stress Index

```bash
curl "http://localhost:8000/api/v1/resources/water-stress?latitude=30.79&longitude=75.84"
```

---

## Step 7: Ask the AI Agent

Submit a natural language question to the multi-agent system:

```bash
curl -X POST http://localhost:8000/api/v1/agents/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What are the environmental risks facing the Western Ghats region?",
    "domains": ["climate", "biodiversity", "health"]
  }'
```

The orchestrator routes your question to the relevant specialist agents and returns a synthesised answer with sources and confidence scores.

---

## Step 8: Generate a Cross-Domain Report

```bash
curl -X POST http://localhost:8000/api/v1/analytics/report \
  -H "Content-Type: application/json" \
  -d '{
    "latitude": 10.5,
    "longitude": 76.5,
    "radius_km": 100,
    "domains": ["climate", "biodiversity", "health", "food_security", "resources"]
  }'
```

---

## Step 9: Explore the Dashboard

Open your browser to [http://localhost:3000](http://localhost:3000) to access the Next.js geospatial dashboard with:

- Interactive map with MapLibre GL and deck.gl
- Domain-specific metric cards
- Alert panel
- Real-time data visualization

---

## Step 10: Explore Additional Tools

### Swagger UI

Browse and test all 42 endpoints interactively:
[http://localhost:8000/api/docs](http://localhost:8000/api/docs)

### Neo4j Browser

Explore the environmental knowledge graph:
[http://localhost:7474](http://localhost:7474) (credentials: `neo4j` / `ecotrack_kg`)

### MLflow UI

View ML experiments and model registry:
[http://localhost:5000](http://localhost:5000)

### MinIO Console

Browse stored datasets and model artifacts:
[http://localhost:9001](http://localhost:9001) (credentials: `minioadmin` / `minioadmin`)

---

## Stopping Services

```bash
docker compose down
```

To also remove stored data volumes:

```bash
docker compose down -v
```

---

## Next Steps

| Goal | Guide |
|------|-------|
| Add a new data source | [Data Ingestion Tutorial](DATA_INGESTION.md) |
| Train an ML model | [Model Training Tutorial](MODEL_TRAINING.md) |
| Build a custom agent | [Agent Development Tutorial](AGENT_DEVELOPMENT.md) |
| Set up for development | [SETUP.md](../../SETUP.md) |
| Full API reference | [API.md](../../API.md) |
| System architecture | [SYSTEM_ARCHITECTURE.md](../architecture/SYSTEM_ARCHITECTURE.md) |
| Contributing | [CONTRIBUTING.md](../../CONTRIBUTING.md) |
