"""Prometheus metrics for EcoTrack services."""
from __future__ import annotations

from prometheus_client import Counter, Histogram, Gauge, Info

# API metrics
REQUEST_COUNT = Counter(
    "ecotrack_api_requests_total",
    "Total API requests",
    ["method", "endpoint", "status_code"],
)
REQUEST_LATENCY = Histogram(
    "ecotrack_api_request_duration_seconds",
    "API request latency",
    ["method", "endpoint"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

# Data pipeline metrics
INGESTION_COUNT = Counter(
    "ecotrack_data_ingestion_total",
    "Total data ingestion operations",
    ["source", "status"],
)
INGESTION_RECORDS = Counter(
    "ecotrack_data_records_ingested_total",
    "Total records ingested",
    ["source", "domain"],
)
INGESTION_LATENCY = Histogram(
    "ecotrack_data_ingestion_duration_seconds",
    "Data ingestion latency",
    ["source"],
)

# ML metrics
MODEL_INFERENCE_COUNT = Counter(
    "ecotrack_ml_inference_total",
    "Total model inference requests",
    ["model_name", "domain"],
)
MODEL_INFERENCE_LATENCY = Histogram(
    "ecotrack_ml_inference_duration_seconds",
    "Model inference latency",
    ["model_name"],
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 5.0],
)
MODEL_PREDICTION_VALUE = Histogram(
    "ecotrack_ml_prediction_value",
    "Distribution of prediction values",
    ["model_name", "variable"],
)

# Agent metrics
AGENT_QUERY_COUNT = Counter(
    "ecotrack_agent_queries_total",
    "Total agent queries",
    ["domain", "agent_role"],
)
AGENT_QUERY_LATENCY = Histogram(
    "ecotrack_agent_query_duration_seconds",
    "Agent query processing latency",
    ["agent_role"],
)

# System metrics
ACTIVE_CONNECTIONS = Gauge(
    "ecotrack_active_connections",
    "Number of active connections",
    ["service"],
)
CACHE_HIT_RATE = Gauge(
    "ecotrack_cache_hit_rate",
    "Cache hit rate",
    ["cache_name"],
)
DB_POOL_SIZE = Gauge(
    "ecotrack_db_pool_size",
    "Database connection pool size",
    ["pool_name"],
)

# Build info
BUILD_INFO = Info("ecotrack_build", "EcoTrack build information")
