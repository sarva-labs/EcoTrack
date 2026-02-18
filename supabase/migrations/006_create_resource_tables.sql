-- ==========================================================================
-- Migration 006: Resource equity domain tables
-- ==========================================================================
-- Creates schema and tables for water stress indices, environmental
-- justice scores, and resource allocation recommendations.
-- ==========================================================================

CREATE SCHEMA IF NOT EXISTS resource_equity;

-- --------------------------------------------------------------------------
-- resource_equity.water_stress  –  water stress assessments
-- --------------------------------------------------------------------------
CREATE TABLE resource_equity.water_stress (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    bbox GEOMETRY(Polygon, 4326) NOT NULL,
    h3_index VARCHAR(15),
    timestamp TIMESTAMPTZ NOT NULL,
    demand_million_m3 DOUBLE PRECISION NOT NULL,
    supply_million_m3 DOUBLE PRECISION NOT NULL,
    stress_ratio DOUBLE PRECISION NOT NULL CHECK (stress_ratio >= 0),
    severity VARCHAR(20) NOT NULL,
    groundwater_depletion_rate DOUBLE PRECISION,
    population_affected INTEGER,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_ws_h3 ON resource_equity.water_stress (h3_index);
CREATE INDEX idx_ws_time ON resource_equity.water_stress (timestamp);
CREATE INDEX idx_ws_severity ON resource_equity.water_stress (severity);
CREATE INDEX idx_ws_ratio ON resource_equity.water_stress (stress_ratio);
CREATE INDEX idx_ws_bbox ON resource_equity.water_stress USING GIST (bbox);

SELECT create_hypertable('resource_equity.water_stress', 'timestamp',
    chunk_time_interval => INTERVAL '3 months',
    if_not_exists => TRUE);

-- --------------------------------------------------------------------------
-- resource_equity.environmental_justice  –  EJ scores per community
-- --------------------------------------------------------------------------
CREATE TABLE resource_equity.environmental_justice (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    bbox GEOMETRY(Polygon, 4326) NOT NULL,
    h3_index VARCHAR(15),
    timestamp TIMESTAMPTZ NOT NULL,
    pollution_burden_score DOUBLE PRECISION CHECK (pollution_burden_score BETWEEN 0 AND 1),
    socioeconomic_vulnerability DOUBLE PRECISION CHECK (socioeconomic_vulnerability BETWEEN 0 AND 1),
    health_disparity_score DOUBLE PRECISION CHECK (health_disparity_score BETWEEN 0 AND 1),
    resource_access_score DOUBLE PRECISION CHECK (resource_access_score BETWEEN 0 AND 1),
    overall_ej_score DOUBLE PRECISION CHECK (overall_ej_score BETWEEN 0 AND 1),
    demographic_indicators JSONB DEFAULT '{}',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_ej_h3 ON resource_equity.environmental_justice (h3_index);
CREATE INDEX idx_ej_time ON resource_equity.environmental_justice (timestamp);
CREATE INDEX idx_ej_overall ON resource_equity.environmental_justice (overall_ej_score);
CREATE INDEX idx_ej_bbox ON resource_equity.environmental_justice USING GIST (bbox);
CREATE INDEX idx_ej_demographics ON resource_equity.environmental_justice USING GIN (demographic_indicators);

SELECT create_hypertable('resource_equity.environmental_justice', 'timestamp',
    chunk_time_interval => INTERVAL '6 months',
    if_not_exists => TRUE);

-- --------------------------------------------------------------------------
-- resource_equity.resource_allocation  –  optimised allocation recommendations
-- --------------------------------------------------------------------------
CREATE TABLE resource_equity.resource_allocation (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    resource_type VARCHAR(50) NOT NULL,
    bbox GEOMETRY(Polygon, 4326) NOT NULL,
    h3_index VARCHAR(15),
    timestamp TIMESTAMPTZ NOT NULL,
    current_allocation DOUBLE PRECISION NOT NULL,
    recommended_allocation DOUBLE PRECISION NOT NULL,
    efficiency_gain_pct DOUBLE PRECISION NOT NULL,
    equity_impact_score DOUBLE PRECISION CHECK (equity_impact_score BETWEEN 0 AND 1),
    rationale TEXT DEFAULT '',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_ra_resource ON resource_equity.resource_allocation (resource_type);
CREATE INDEX idx_ra_h3 ON resource_equity.resource_allocation (h3_index);
CREATE INDEX idx_ra_time ON resource_equity.resource_allocation (timestamp);
CREATE INDEX idx_ra_bbox ON resource_equity.resource_allocation USING GIST (bbox);

SELECT create_hypertable('resource_equity.resource_allocation', 'timestamp',
    chunk_time_interval => INTERVAL '3 months',
    if_not_exists => TRUE);

-- --------------------------------------------------------------------------
-- Pipeline metadata schema for data pipeline blob storage
-- --------------------------------------------------------------------------
CREATE SCHEMA IF NOT EXISTS pipeline;

CREATE TABLE IF NOT EXISTS pipeline.stored_objects (
    key VARCHAR(512) PRIMARY KEY,
    data BYTEA NOT NULL,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_so_prefix ON pipeline.stored_objects USING btree (key varchar_pattern_ops);

-- --------------------------------------------------------------------------
-- Ingestion tracking – records pipeline run metadata
-- --------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS pipeline.ingestion_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_name VARCHAR(100) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ,
    total_records INTEGER DEFAULT 0,
    total_duration_s DOUBLE PRECISION,
    error_message TEXT,
    parameters JSONB DEFAULT '{}',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_ir_source ON pipeline.ingestion_runs (source_name);
CREATE INDEX idx_ir_status ON pipeline.ingestion_runs (status);
CREATE INDEX idx_ir_started ON pipeline.ingestion_runs (started_at);
