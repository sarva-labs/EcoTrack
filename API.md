# EcoTrack API Reference

Complete reference for the EcoTrack REST API. The API is built with [FastAPI](https://fastapi.tiangolo.com/) and serves environmental intelligence across 5 domains plus cross-cutting analytics, AI agents, and data pipeline management.

**Base URL**: `http://localhost:8000`
**Interactive Docs**: [`/api/docs`](http://localhost:8000/api/docs) (Swagger UI) · [`/api/redoc`](http://localhost:8000/api/redoc) (ReDoc)
**OpenAPI Spec**: [`/api/openapi.json`](http://localhost:8000/api/openapi.json)

---

## Table of Contents

- [Authentication](#authentication)
- [Rate Limiting](#rate-limiting)
- [Pagination](#pagination)
- [Error Handling](#error-handling)
- [System Endpoints](#system-endpoints)
- [Climate](#climate)
- [Biodiversity](#biodiversity)
- [Public Health](#public-health)
- [Food Security](#food-security)
- [Resource Equity](#resource-equity)
- [AI Agents](#ai-agents)
- [Analytics](#analytics)
- [Data Pipeline](#data-pipeline)
- [WebSocket](#websocket)
- [Error Codes Reference](#error-codes-reference)

---

## Authentication

EcoTrack supports two authentication methods: **JWT Bearer tokens** and **API keys**.

### JWT Bearer Token

Include the token in the `Authorization` header:

```bash
curl -H "Authorization: Bearer <your-jwt-token>" \
  http://localhost:8000/api/v1/climate/observations
```

JWT tokens contain the following claims:

| Claim | Type | Description |
|-------|------|-------------|
| `sub` | `string` | User ID |
| `role` | `string` | User role: `public`, `researcher`, `admin` |
| `exp` | `datetime` | Token expiration time |
| `iat` | `datetime` | Token issued-at time |

### API Key

Include the key in the `X-API-Key` header:

```bash
curl -H "X-API-Key: eco_your_api_key_here" \
  http://localhost:8000/api/v1/climate/observations
```

API keys must start with the `eco_` prefix.

### Anonymous Access

Endpoints are accessible without authentication at the `public` role level with reduced rate limits.

### User Roles

| Role | Access Level | Description |
|------|-------------|-------------|
| `public` | Read-only, limited | Anonymous or unauthenticated access |
| `researcher` | Read/write, extended | Authenticated researchers and developers |
| `admin` | Full access | Platform administrators |

---

## Rate Limiting

Requests are rate-limited per user based on role:

| Role | Requests/Minute | Requests/Day |
|------|----------------|-------------|
| `public` | 30 | 1,000 |
| `researcher` | 120 | 10,000 |
| `admin` | 600 | 100,000 |

Rate limit headers are included in every response:

```
X-RateLimit-Limit: 120
X-RateLimit-Remaining: 117
X-RateLimit-Reset: 1708228800
```

When rate-limited, the API returns `429 Too Many Requests`.

---

## Pagination

All list endpoints return paginated responses using the following query parameters:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `page` | `int` | `1` | Page number (1-based) |
| `page_size` | `int` | `50` | Items per page (max 1000) |

Paginated response format:

```json
{
  "items": [...],
  "total": 142,
  "page": 1,
  "page_size": 50,
  "has_next": true
}
```

---

## Error Handling

All errors follow a consistent JSON format:

```json
{
  "detail": "Description of what went wrong"
}
```

For validation errors (422):

```json
{
  "detail": [
    {
      "loc": ["query", "variable"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

---

## System Endpoints

### Health Check

```
GET /api/health
```

Returns the service health status.

```bash
curl http://localhost:8000/api/health
```

```json
{
  "status": "healthy",
  "version": "0.1.0",
  "service": "ecotrack-api"
}
```

### List Domains

```
GET /api/v1/domains
```

Lists all available EcoTrack domain endpoints.

```bash
curl http://localhost:8000/api/v1/domains
```

```json
{
  "domains": [
    {"name": "climate", "description": "Climate intelligence and forecasting", "endpoints": "/api/v1/climate"},
    {"name": "biodiversity", "description": "Biodiversity monitoring and assessment", "endpoints": "/api/v1/biodiversity"},
    {"name": "health", "description": "Public health and environmental health", "endpoints": "/api/v1/health"},
    {"name": "food_security", "description": "Food security and agricultural monitoring", "endpoints": "/api/v1/food-security"},
    {"name": "resources", "description": "Resource equity and allocation", "endpoints": "/api/v1/resources"},
    {"name": "agents", "description": "AI agent interaction and orchestration", "endpoints": "/api/v1/agents"},
    {"name": "analytics", "description": "Cross-domain analytics and reporting", "endpoints": "/api/v1/analytics"},
    {"name": "data", "description": "Data pipeline and catalog management", "endpoints": "/api/v1/data"}
  ]
}
```

---

## Climate

**Base path**: `/api/v1/climate`

### Query Climate Observations

```
GET /api/v1/climate/observations
```

Query climate observations with spatial, temporal, and variable filters.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `variable` | `string` | No | Climate variable: `temperature`, `precipitation`, `humidity`, `wind_speed`, `pressure` |
| `min_lon` | `float` | No | Bounding box minimum longitude (-180 to 180) |
| `min_lat` | `float` | No | Bounding box minimum latitude (-90 to 90) |
| `max_lon` | `float` | No | Bounding box maximum longitude (-180 to 180) |
| `max_lat` | `float` | No | Bounding box maximum latitude (-90 to 90) |
| `start_time` | `datetime` | No | Start of time window (ISO 8601) |
| `end_time` | `datetime` | No | End of time window (ISO 8601) |
| `source` | `string` | No | Data source filter: `ERA5`, `NOAA`, `ECMWF` |
| `page` | `int` | No | Page number (default: 1) |
| `page_size` | `int` | No | Items per page (default: 50, max: 1000) |

```bash
curl "http://localhost:8000/api/v1/climate/observations?variable=temperature&min_lat=28&max_lat=30&min_lon=76&max_lon=78"
```

```json
{
  "items": [
    {
      "id": "obs-clim-0000",
      "variable": "temperature",
      "value": 15.0,
      "unit": "°C",
      "latitude": 40.0,
      "longitude": -74.0,
      "elevation_m": 50.0,
      "timestamp": "2026-02-18T04:00:00Z",
      "source": "ERA5",
      "quality_flag": "good"
    }
  ],
  "total": 142,
  "page": 1,
  "page_size": 50,
  "has_next": true
}
```

### Generate Climate Forecast

```
POST /api/v1/climate/forecast
```

Generate a climate forecast for a specified region and variable.

**Request body:**

```json
{
  "variable": "temperature",
  "min_lon": 76.0,
  "min_lat": 28.0,
  "max_lon": 78.0,
  "max_lat": 30.0,
  "forecast_horizon_hours": 72,
  "model": "tcn-v3"
}
```

```bash
curl -X POST http://localhost:8000/api/v1/climate/forecast \
  -H "Content-Type: application/json" \
  -d '{"variable": "temperature", "min_lon": 76.0, "min_lat": 28.0, "max_lon": 78.0, "max_lat": 30.0, "forecast_horizon_hours": 72, "model": "tcn-v3"}'
```

**Response** (201 Created):

```json
{
  "forecast_id": "fcst-20260218-001",
  "variable": "temperature",
  "unit": "°C",
  "model_used": "tcn-v3",
  "generated_at": "2026-02-18T04:00:00Z",
  "horizon_hours": 72,
  "bbox": {"min_lon": 76.0, "min_lat": 28.0, "max_lon": 78.0, "max_lat": 30.0},
  "forecast_points": [
    {
      "timestamp": "2026-02-18T04:00:00Z",
      "value": 18.0,
      "lower_ci": 16.5,
      "upper_ci": 19.5
    }
  ],
  "metadata": {"resolution_km": 25, "ensemble_members": 30}
}
```

### Query Climate Anomalies

```
GET /api/v1/climate/anomalies
```

Query detected climate anomalies, filtered by severity and region.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `variable` | `string` | No | Climate variable filter |
| `severity` | `string` | No | Severity: `info`, `low`, `medium`, `high`, `critical` |
| `min_lon`, `min_lat`, `max_lon`, `max_lat` | `float` | No | Bounding box |
| `start_time`, `end_time` | `datetime` | No | Time window |

```bash
curl "http://localhost:8000/api/v1/climate/anomalies?severity=high"
```

```json
{
  "items": [
    {
      "id": "anom-001",
      "variable": "temperature",
      "observed_value": 38.5,
      "expected_value": 31.2,
      "deviation": 3.2,
      "severity": "high",
      "latitude": 28.6139,
      "longitude": 77.209,
      "detected_at": "2026-02-18T02:00:00Z",
      "description": "Temperature 3.2σ above seasonal mean for Delhi NCR region"
    }
  ],
  "total": 2,
  "page": 1,
  "page_size": 50,
  "has_next": false
}
```

### Analyse Climate Trends

```
GET /api/v1/climate/trends
```

Compute long-term climate trends for a region with linear regression.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `variable` | `string` | **Yes** | Climate variable to analyse |
| `min_lon`, `min_lat`, `max_lon`, `max_lat` | `float` | No | Bounding box |
| `period_years` | `int` | No | Analysis period (default: 10, max: 100) |

```bash
curl "http://localhost:8000/api/v1/climate/trends?variable=temperature&period_years=30"
```

### List Climate Variables

```
GET /api/v1/climate/variables
```

List all climate variables available in the platform with their units and sources.

```bash
curl http://localhost:8000/api/v1/climate/variables
```

---

## Biodiversity

**Base path**: `/api/v1/biodiversity`

### Search Species

```
GET /api/v1/biodiversity/species
```

Search species with spatial and conservation status filters.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `name` | `string` | No | Species name (scientific or common) |
| `conservation_status` | `string` | No | IUCN Red List status: `VU`, `EN`, `CR`, etc. |
| `min_lon`, `min_lat`, `max_lon`, `max_lat` | `float` | No | Bounding box |

```bash
curl "http://localhost:8000/api/v1/biodiversity/species?conservation_status=EN"
```

```json
{
  "items": [
    {
      "species_name": "Panthera tigris",
      "common_name": "Bengal Tiger",
      "conservation_status": "EN",
      "observation_count": 1247,
      "last_observed": "2026-02-15T04:00:00Z",
      "range_description": "South and Southeast Asia"
    }
  ],
  "total": 2,
  "page": 1,
  "page_size": 50,
  "has_next": false
}
```

### Get Species Observations

```
GET /api/v1/biodiversity/species/{species_name}/observations
```

Get observation records for a specific species, sourced from GBIF and partner networks.

```bash
curl "http://localhost:8000/api/v1/biodiversity/species/Panthera%20tigris/observations"
```

### Query Observations by Region

```
GET /api/v1/biodiversity/observations
```

Query all species observations within a bounding box and time range.

### Get Ecosystem Health Index

```
GET /api/v1/biodiversity/ecosystem-health
```

Get the composite ecosystem health index combining species richness, diversity, threats, and habitat integrity.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `latitude` | `float` | **Yes** | Region centre latitude |
| `longitude` | `float` | **Yes** | Region centre longitude |
| `radius_km` | `float` | No | Analysis radius (default: 50, max: 500) |

```bash
curl "http://localhost:8000/api/v1/biodiversity/ecosystem-health?latitude=10.5&longitude=76.5&radius_km=100"
```

```json
{
  "region_name": "Western Ghats Biodiversity Hotspot",
  "latitude": 10.5,
  "longitude": 76.5,
  "health_index": 0.72,
  "species_richness": 1842,
  "shannon_diversity": 4.31,
  "threatened_species_count": 187,
  "invasive_species_count": 23,
  "habitat_integrity": 0.68,
  "trend": "declining",
  "assessed_at": "2026-02-18T04:00:00Z"
}
```

### Identify Biodiversity Hotspots

```
GET /api/v1/biodiversity/hotspots
```

Identify areas with exceptionally high species richness and endemism.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `min_lon`, `min_lat`, `max_lon`, `max_lat` | `float` | No | Bounding box |
| `threat_level` | `string` | No | Filter: `low`, `medium`, `high`, `critical` |

### Get Conservation Status Summary

```
GET /api/v1/biodiversity/conservation-status
```

Summary of IUCN conservation statuses for species in a region.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `latitude` | `float` | **Yes** | Region centre latitude |
| `longitude` | `float` | **Yes** | Region centre longitude |
| `radius_km` | `float` | No | Analysis radius (default: 100) |

---

## Public Health

**Base path**: `/api/v1/health`

### Current Air Quality

```
GET /api/v1/health/air-quality
```

Real-time AQI readings from monitoring stations (OpenAQ, EPA AirNow).

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `min_lon`, `min_lat`, `max_lon`, `max_lat` | `float` | No | Bounding box |
| `pollutant` | `string` | No | Filter: `PM2.5`, `PM10`, `O3`, `NO2`, `SO2`, `CO` |
| `min_aqi` | `int` | No | Minimum AQI threshold |

```bash
curl "http://localhost:8000/api/v1/health/air-quality?min_lat=28&max_lat=29&min_lon=77&max_lon=78&pollutant=PM2.5"
```

```json
{
  "items": [
    {
      "station_id": "AQ-DEL-001",
      "latitude": 28.6139,
      "longitude": 77.209,
      "aqi": 156,
      "category": "Unhealthy",
      "dominant_pollutant": "PM2.5",
      "pollutants": [
        {"pollutant": "PM2.5", "value": 65.4, "unit": "µg/m³", "aqi_contribution": 156},
        {"pollutant": "PM10", "value": 112.0, "unit": "µg/m³", "aqi_contribution": 80}
      ],
      "measured_at": "2026-02-18T03:45:00Z",
      "source": "OpenAQ"
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 50,
  "has_next": false
}
```

### Air Quality Forecast

```
GET /api/v1/health/air-quality/forecast
```

Hourly AQI predictions for up to 120 hours.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `latitude` | `float` | **Yes** | Latitude |
| `longitude` | `float` | **Yes** | Longitude |
| `hours` | `int` | No | Forecast horizon (default: 48, max: 120) |

### Disease Vector Risk Assessment

```
GET /api/v1/health/disease-risk
```

Location-specific disease vector risk combining environmental conditions, habitat suitability, and incidence data.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `latitude` | `float` | **Yes** | Latitude |
| `longitude` | `float` | **Yes** | Longitude |
| `disease` | `string` | No | Filter: `malaria`, `dengue`, `zika`, `chikungunya` |

```bash
curl "http://localhost:8000/api/v1/health/disease-risk?latitude=19.07&longitude=72.87"
```

### Heat Vulnerability Mapping

```
GET /api/v1/health/heat-vulnerability
```

Heat vulnerability index combining exposure, sensitivity, and adaptive capacity.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `latitude` | `float` | **Yes** | Latitude |
| `longitude` | `float` | **Yes** | Longitude |

### Water Quality Index

```
GET /api/v1/health/water-quality
```

Composite Water Quality Index for the nearest monitored water body.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `latitude` | `float` | **Yes** | Latitude |
| `longitude` | `float` | **Yes** | Longitude |

---

## Food Security

**Base path**: `/api/v1/food-security`

### Crop Yield Predictions

```
GET /api/v1/food-security/crop-yield
```

ML-generated yield predictions with confidence intervals and key drivers.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `crop_type` | `string` | No | Crop filter: `wheat`, `rice`, `maize`, `soybean`, etc. |
| `min_lon`, `min_lat`, `max_lon`, `max_lat` | `float` | No | Bounding box |

```bash
curl "http://localhost:8000/api/v1/food-security/crop-yield?crop_type=wheat"
```

```json
{
  "items": [
    {
      "prediction_id": "cyp-2026-001",
      "crop_type": "wheat",
      "region_name": "Punjab, India",
      "latitude": 30.79,
      "longitude": 75.84,
      "predicted_yield_tonnes_ha": 4.82,
      "yield_lower_ci": 4.35,
      "yield_upper_ci": 5.29,
      "historical_avg_yield": 4.50,
      "yield_change_pct": 7.1,
      "growing_season": "2026-rabi",
      "model_used": "EcoTrack-CropNet-v3",
      "key_factors": {"soil_moisture": 0.35, "temperature": 0.28, "rainfall": 0.22, "fertilizer": 0.15},
      "predicted_at": "2026-02-17T16:00:00Z"
    }
  ],
  "total": 2,
  "page": 1,
  "page_size": 50,
  "has_next": false
}
```

### Generate Crop Yield Prediction

```
POST /api/v1/food-security/crop-yield/predict
```

Generate a new crop yield prediction for a specific location and crop.

**Request body:**

```json
{
  "crop_type": "rice",
  "latitude": 10.04,
  "longitude": 105.72,
  "soil_type": "alluvial",
  "irrigation_type": "irrigated"
}
```

### Active Drought Alerts

```
GET /api/v1/food-security/drought-alerts
```

Active drought monitor alerts with SPI/SPEI and impact assessments.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `severity` | `string` | No | Drought severity: `D0`–`D4` |
| `min_lon`, `min_lat`, `max_lon`, `max_lat` | `float` | No | Bounding box |

### Food Security Index

```
GET /api/v1/food-security/food-security-index
```

IPC-aligned food security classification with dimension scores.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `latitude` | `float` | **Yes** | Region centre latitude |
| `longitude` | `float` | **Yes** | Region centre longitude |

### List Crop Types

```
GET /api/v1/food-security/crop-types
```

All crop types supported by the yield prediction system.

---

## Resource Equity

**Base path**: `/api/v1/resources`

### Water Stress Index

```
GET /api/v1/resources/water-stress
```

Water stress using the Aqueduct methodology (supply-demand ratio, groundwater depletion, drought risk).

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `latitude` | `float` | **Yes** | Latitude |
| `longitude` | `float` | **Yes** | Longitude |

```bash
curl "http://localhost:8000/api/v1/resources/water-stress?latitude=30.79&longitude=75.84"
```

```json
{
  "region_name": "North-West India — Punjab-Haryana",
  "latitude": 30.79,
  "longitude": 75.84,
  "stress_index": 4.2,
  "stress_level": "extremely_high",
  "water_demand_m3_day": 285000000,
  "water_supply_m3_day": 195000000,
  "supply_demand_ratio": 0.68,
  "groundwater_depletion_rate": 12.5,
  "seasonal_variability": "high",
  "drought_risk": "high",
  "assessed_at": "2026-02-18T04:00:00Z"
}
```

### Environmental Justice Assessment

```
GET /api/v1/resources/environmental-justice
```

Composite EJ index from pollution burden, health disparities, and socio-economic factors.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `latitude` | `float` | **Yes** | Latitude |
| `longitude` | `float` | **Yes** | Longitude |

```bash
curl "http://localhost:8000/api/v1/resources/environmental-justice?latitude=29.76&longitude=-95.36"
```

### Optimise Resource Allocation

```
POST /api/v1/resources/allocate
```

RL-based resource allocation optimisation across regions.

**Request body:**

```json
{
  "resource_type": "water",
  "total_budget": 10000000,
  "region_ids": ["region-01", "region-02", "region-03"],
  "optimisation_objective": "equity"
}
```

**Response** (201 Created):

```json
{
  "allocation_id": "alloc-2026-001",
  "resource_type": "water",
  "total_budget": 10000000,
  "objective": "equity",
  "allocations": [
    {
      "region_id": "region-01",
      "region_name": "Region region-01",
      "allocated_amount": 2666666.67,
      "allocation_pct": 33.3,
      "need_score": 0.5,
      "equity_score": 0.7,
      "rationale": "Allocation based on equity objective with need weighting"
    }
  ],
  "overall_equity_score": 0.82,
  "overall_efficiency_score": 0.78,
  "generated_at": "2026-02-18T04:00:00Z"
}
```

### Energy Distribution Equity

```
GET /api/v1/resources/energy-distribution
```

Energy access rates, renewable share, consumption, and poverty indicators.

### List Resource Types

```
GET /api/v1/resources/resource-types
```

All resource types tracked by the platform.

---

## AI Agents

**Base path**: `/api/v1/agents`

### Submit Natural Language Query

```
POST /api/v1/agents/query
```

Submit a natural language query to the multi-agent system. The orchestrator routes the query to relevant specialist agents and synthesises their responses.

**Request body:**

```json
{
  "query": "How has deforestation in Borneo affected local biodiversity over the past decade?",
  "context": {},
  "domains": ["biodiversity", "climate"]
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `query` | `string` | **Yes** | Natural language question |
| `context` | `object` | No | Additional context |
| `domains` | `string[]` | No | Restrict to specific domains |

```bash
curl -X POST http://localhost:8000/api/v1/agents/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What are the current temperature trends in the Amazon basin?", "domains": ["climate"]}'
```

**Response:**

```json
{
  "query_id": "aq-a1b2c3d4e5f6",
  "answer": "Based on analysis across 3 specialist agents: The query has been processed...",
  "sources": [
    {"source_type": "dataset", "name": "ERA5 Climate Reanalysis", "url": "https://cds.climate.copernicus.eu/", "relevance_score": 0.92},
    {"source_type": "model_output", "name": "EcoTrack Climate Forecaster v3", "relevance_score": 0.88},
    {"source_type": "dataset", "name": "GBIF Species Occurrences", "url": "https://www.gbif.org/", "relevance_score": 0.75}
  ],
  "agents_consulted": ["climate_specialist", "biodiversity_specialist", "health_specialist"],
  "confidence": 0.85,
  "processing_time_ms": 1247.5,
  "follow_up_suggestions": [
    "What are the specific climate anomalies in this region?",
    "Show me biodiversity hotspot threats near this area",
    "What is the food security outlook for the next 6 months?"
  ]
}
```

### Agent System Status

```
GET /api/v1/agents/status
```

Current status of the agent system including active agents and processing statistics.

```bash
curl http://localhost:8000/api/v1/agents/status
```

```json
{
  "status": "operational",
  "active_agents": 5,
  "available_tools": 12,
  "queries_processed_today": 342,
  "average_response_time_ms": 1150.0,
  "uptime_hours": 168.5
}
```

### List Agent Tools

```
GET /api/v1/agents/tools
```

All tools available to the agent system.

---

## Analytics

**Base path**: `/api/v1/analytics`

### Dashboard Summary

```
GET /api/v1/analytics/dashboard-summary
```

Aggregate metrics across all domains for a region — the single-view dashboard endpoint.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `latitude` | `float` | **Yes** | Region centre latitude |
| `longitude` | `float` | **Yes** | Region centre longitude |
| `radius_km` | `float` | No | Analysis radius (default: 50) |

```bash
curl "http://localhost:8000/api/v1/analytics/dashboard-summary?latitude=19.07&longitude=76.15&radius_km=100"
```

### Run Causal Analysis

```
POST /api/v1/analytics/causal-analysis
```

Discover causal relationships between environmental variables using Granger causality and do-calculus.

**Request body:**

```json
{
  "variables": ["temperature_anomaly", "crop_yield", "water_stress"],
  "min_lon": 70.0,
  "min_lat": 15.0,
  "max_lon": 85.0,
  "max_lat": 30.0
}
```

**Response** (201 Created):

```json
{
  "analysis_id": "causal-20260218120000",
  "variables": ["temperature_anomaly", "crop_yield", "water_stress"],
  "causal_links": [
    {
      "cause": "temperature_anomaly",
      "effect": "crop_yield",
      "strength": 0.6,
      "confidence": 0.8,
      "lag_days": 14,
      "mechanism": "temperature_anomaly affects crop_yield through environmental feedback loops"
    }
  ],
  "summary": "Causal analysis of 3 variables identified 2 significant causal links.",
  "generated_at": "2026-02-18T12:00:00Z"
}
```

### Cross-Domain Correlations

```
GET /api/v1/analytics/correlations
```

Statistically significant correlations between variables from different domains.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `min_lon`, `min_lat`, `max_lon`, `max_lat` | `float` | No | Bounding box |
| `min_correlation` | `float` | No | Minimum absolute correlation (default: 0.5) |

### All Active Alerts

```
GET /api/v1/analytics/alerts
```

Aggregated alerts from all domains.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `severity` | `string` | No | Filter: `info`, `low`, `medium`, `high`, `critical` |
| `domain` | `string` | No | Filter by domain |

```bash
curl "http://localhost:8000/api/v1/analytics/alerts?severity=critical"
```

### Generate Comprehensive Report

```
POST /api/v1/analytics/report
```

Generate a structured environmental report synthesising data from all requested domains.

**Request body:**

```json
{
  "latitude": 19.07,
  "longitude": 76.15,
  "radius_km": 100,
  "domains": ["climate", "biodiversity", "health", "food_security", "resources"],
  "format": "json"
}
```

---

## Data Pipeline

**Base path**: `/api/v1/data`

### List Data Sources

```
GET /api/v1/data/sources
```

All data sources available for ingestion with metadata.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `domain` | `string` | No | Filter by domain |
| `status` | `string` | No | Filter: `active`, `degraded`, `offline` |

```bash
curl "http://localhost:8000/api/v1/data/sources?domain=climate"
```

```json
[
  {
    "source_id": "era5",
    "name": "ERA5 Climate Reanalysis",
    "provider": "ECMWF / Copernicus",
    "domains": ["climate"],
    "update_frequency": "daily",
    "spatial_resolution": "0.25°",
    "temporal_coverage": "1940-present",
    "format": "netcdf",
    "status": "active",
    "last_updated": "2026-02-17T22:00:00Z"
  }
]
```

### Trigger Data Ingestion

```
POST /api/v1/data/ingest
```

Enqueue a data ingestion job for asynchronous processing.

**Request body:**

```json
{
  "source_id": "era5",
  "parameters": {"variable": "temperature", "year": 2026, "month": 2},
  "priority": "high"
}
```

**Response** (202 Accepted):

```json
{
  "job_id": "ingest-a1b2c3d4e5f6",
  "source_id": "era5",
  "status": "queued",
  "progress_pct": 0.0,
  "records_processed": 0,
  "records_total": null,
  "error_message": null,
  "started_at": null,
  "completed_at": null,
  "created_at": "2026-02-18T04:00:00Z"
}
```

### List Ingestion Jobs

```
GET /api/v1/data/jobs
```

List ingestion jobs with optional status/source filters.

### Get Job Details

```
GET /api/v1/data/jobs/{job_id}
```

Detailed status of a specific ingestion job.

### Search Data Catalog

```
GET /api/v1/data/catalog
```

Browse available datasets with spatial, domain, and free-text filters.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `query` | `string` | No | Free-text search |
| `domain` | `string` | No | Filter by domain |
| `min_lon`, `min_lat`, `max_lon`, `max_lat` | `float` | No | Bounding box |

---

## WebSocket

### Agent WebSocket

```
WS /api/v1/agents/ws
```

Real-time agent interaction via WebSocket. Clients send JSON messages and receive streaming status updates as the agent system processes queries.

**Connect:**

```javascript
const ws = new WebSocket("ws://localhost:8000/api/v1/agents/ws");

ws.onopen = () => {
  ws.send(JSON.stringify({
    query: "What is the air quality forecast for Delhi this week?",
    domains: ["health", "climate"]
  }));
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log(data.type, data.message || data.answer);
};
```

**Server messages:**

Status update:
```json
{
  "type": "status",
  "query_id": "ws-a1b2c3d4",
  "message": "Climate specialist responding..."
}
```

Final answer:
```json
{
  "type": "answer",
  "query_id": "ws-a1b2c3d4",
  "answer": "Analysis of the query...",
  "confidence": 0.82,
  "agents_consulted": ["climate_specialist", "biodiversity_specialist"],
  "timestamp": "2026-02-18T04:00:00Z"
}
```

---

## Error Codes Reference

| Status Code | Meaning | Common Causes |
|-------------|---------|---------------|
| `200` | OK | Successful GET request |
| `201` | Created | Successful POST (forecast, prediction, analysis) |
| `202` | Accepted | Job enqueued for async processing |
| `400` | Bad Request | Malformed request body |
| `401` | Unauthorized | Missing, expired, or invalid token/API key |
| `403` | Forbidden | Insufficient role permissions |
| `404` | Not Found | Resource or endpoint does not exist |
| `422` | Unprocessable Entity | Request validation failed (see detail array) |
| `429` | Too Many Requests | Rate limit exceeded |
| `500` | Internal Server Error | Unexpected server error |
| `503` | Service Unavailable | Backend service temporarily down |

---

## Endpoint Summary

| # | Method | Path | Description | Auth |
|---|--------|------|-------------|------|
| 1 | GET | `/api/health` | Health check | — |
| 2 | GET | `/api/v1/domains` | List domains | — |
| 3 | GET | `/api/v1/climate/observations` | Climate observations | Public |
| 4 | POST | `/api/v1/climate/forecast` | Generate forecast | Researcher |
| 5 | GET | `/api/v1/climate/anomalies` | Climate anomalies | Public |
| 6 | GET | `/api/v1/climate/trends` | Climate trends | Public |
| 7 | GET | `/api/v1/climate/variables` | List variables | Public |
| 8 | GET | `/api/v1/biodiversity/species` | Search species | Public |
| 9 | GET | `/api/v1/biodiversity/species/{name}/observations` | Species observations | Public |
| 10 | GET | `/api/v1/biodiversity/observations` | Regional observations | Public |
| 11 | GET | `/api/v1/biodiversity/ecosystem-health` | Ecosystem health | Public |
| 12 | GET | `/api/v1/biodiversity/hotspots` | Biodiversity hotspots | Public |
| 13 | GET | `/api/v1/biodiversity/conservation-status` | Conservation summary | Public |
| 14 | GET | `/api/v1/health/air-quality` | Air quality readings | Public |
| 15 | GET | `/api/v1/health/air-quality/forecast` | AQ forecast | Public |
| 16 | GET | `/api/v1/health/disease-risk` | Disease vector risk | Public |
| 17 | GET | `/api/v1/health/heat-vulnerability` | Heat vulnerability | Public |
| 18 | GET | `/api/v1/health/water-quality` | Water quality | Public |
| 19 | GET | `/api/v1/food-security/crop-yield` | Yield predictions | Public |
| 20 | POST | `/api/v1/food-security/crop-yield/predict` | Generate prediction | Researcher |
| 21 | GET | `/api/v1/food-security/drought-alerts` | Drought alerts | Public |
| 22 | GET | `/api/v1/food-security/food-security-index` | Food security index | Public |
| 23 | GET | `/api/v1/food-security/crop-types` | List crop types | Public |
| 24 | GET | `/api/v1/resources/water-stress` | Water stress | Public |
| 25 | GET | `/api/v1/resources/environmental-justice` | EJ assessment | Public |
| 26 | POST | `/api/v1/resources/allocate` | Resource allocation | Researcher |
| 27 | GET | `/api/v1/resources/energy-distribution` | Energy equity | Public |
| 28 | GET | `/api/v1/resources/resource-types` | List resource types | Public |
| 29 | POST | `/api/v1/agents/query` | Agent query | Public |
| 30 | GET | `/api/v1/agents/status` | Agent status | Public |
| 31 | GET | `/api/v1/agents/tools` | List tools | Public |
| 32 | WS | `/api/v1/agents/ws` | Agent WebSocket | Public |
| 33 | GET | `/api/v1/analytics/dashboard-summary` | Dashboard metrics | Public |
| 34 | POST | `/api/v1/analytics/causal-analysis` | Causal analysis | Researcher |
| 35 | GET | `/api/v1/analytics/correlations` | Cross-domain correlations | Public |
| 36 | GET | `/api/v1/analytics/alerts` | All alerts | Public |
| 37 | POST | `/api/v1/analytics/report` | Generate report | Researcher |
| 38 | GET | `/api/v1/data/sources` | List data sources | Public |
| 39 | POST | `/api/v1/data/ingest` | Trigger ingestion | Researcher |
| 40 | GET | `/api/v1/data/jobs` | List ingestion jobs | Public |
| 41 | GET | `/api/v1/data/jobs/{job_id}` | Job details | Public |
| 42 | GET | `/api/v1/data/catalog` | Search catalog | Public |

---

*This API reference is auto-generated from the OpenAPI spec. For interactive testing, use [Swagger UI](http://localhost:8000/api/docs).*
