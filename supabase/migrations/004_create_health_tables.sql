-- ==========================================================================
-- Migration 004: Public health domain tables
-- ==========================================================================
-- Creates schema and tables for air quality measurements, disease vector
-- risk assessments, and heat vulnerability indices.
-- ==========================================================================

CREATE SCHEMA IF NOT EXISTS public_health;

-- --------------------------------------------------------------------------
-- public_health.air_quality  –  ground-level air quality readings
-- --------------------------------------------------------------------------
CREATE TABLE public_health.air_quality (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location GEOMETRY(Point, 4326) NOT NULL,
    h3_index VARCHAR(15) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    aqi INTEGER CHECK (aqi BETWEEN 0 AND 500),
    pm25 DOUBLE PRECISION,
    pm10 DOUBLE PRECISION,
    ozone DOUBLE PRECISION,
    no2 DOUBLE PRECISION,
    so2 DOUBLE PRECISION,
    co DOUBLE PRECISION,
    source VARCHAR(100),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_aq_h3 ON public_health.air_quality (h3_index);
CREATE INDEX idx_aq_time ON public_health.air_quality (timestamp);
CREATE INDEX idx_aq_location ON public_health.air_quality USING GIST (location);
CREATE INDEX idx_aq_aqi ON public_health.air_quality (aqi);
CREATE INDEX idx_aq_source ON public_health.air_quality (source);

SELECT create_hypertable('public_health.air_quality', 'timestamp',
    chunk_time_interval => INTERVAL '1 month',
    if_not_exists => TRUE);

-- --------------------------------------------------------------------------
-- public_health.disease_vector_risk  –  vector-borne disease risk scores
-- --------------------------------------------------------------------------
CREATE TABLE public_health.disease_vector_risk (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    disease VARCHAR(100) NOT NULL,
    vector VARCHAR(100) NOT NULL,
    bbox GEOMETRY(Polygon, 4326) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    risk_score DOUBLE PRECISION CHECK (risk_score BETWEEN 0 AND 1),
    severity VARCHAR(20) NOT NULL,
    contributing_factors TEXT[],
    population_at_risk INTEGER,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_dvr_disease ON public_health.disease_vector_risk (disease);
CREATE INDEX idx_dvr_time ON public_health.disease_vector_risk (timestamp);
CREATE INDEX idx_dvr_severity ON public_health.disease_vector_risk (severity);
CREATE INDEX idx_dvr_bbox ON public_health.disease_vector_risk USING GIST (bbox);

-- --------------------------------------------------------------------------
-- public_health.heat_vulnerability  –  urban heat vulnerability assessments
-- --------------------------------------------------------------------------
CREATE TABLE public_health.heat_vulnerability (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    bbox GEOMETRY(Polygon, 4326) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    temperature_c DOUBLE PRECISION NOT NULL,
    heat_index_c DOUBLE PRECISION NOT NULL,
    vulnerability_score DOUBLE PRECISION CHECK (vulnerability_score BETWEEN 0 AND 1),
    urban_heat_island_effect DOUBLE PRECISION,
    at_risk_population INTEGER,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_hv_time ON public_health.heat_vulnerability (timestamp);
CREATE INDEX idx_hv_score ON public_health.heat_vulnerability (vulnerability_score);
CREATE INDEX idx_hv_bbox ON public_health.heat_vulnerability USING GIST (bbox);

SELECT create_hypertable('public_health.heat_vulnerability', 'timestamp',
    chunk_time_interval => INTERVAL '1 month',
    if_not_exists => TRUE);
