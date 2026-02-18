-- ==========================================================================
-- Migration 005: Food security domain tables
-- ==========================================================================
-- Creates schema and tables for crop yield predictions, drought alerts,
-- food security indices, and crop land-cover data.
-- ==========================================================================

CREATE SCHEMA IF NOT EXISTS food_security;

-- --------------------------------------------------------------------------
-- food_security.crop_yields  –  ML-predicted crop yields per region
-- --------------------------------------------------------------------------
CREATE TABLE food_security.crop_yields (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    crop_type VARCHAR(50) NOT NULL,
    bbox GEOMETRY(Polygon, 4326) NOT NULL,
    prediction_date TIMESTAMPTZ NOT NULL,
    harvest_date TIMESTAMPTZ NOT NULL,
    predicted_yield_tons_per_ha DOUBLE PRECISION NOT NULL,
    yield_lower_bound DOUBLE PRECISION NOT NULL,
    yield_upper_bound DOUBLE PRECISION NOT NULL,
    historical_avg_yield DOUBLE PRECISION NOT NULL,
    model_name VARCHAR(100) NOT NULL,
    confidence DOUBLE PRECISION CHECK (confidence BETWEEN 0 AND 1),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_cy_crop ON food_security.crop_yields (crop_type);
CREATE INDEX idx_cy_prediction ON food_security.crop_yields (prediction_date);
CREATE INDEX idx_cy_harvest ON food_security.crop_yields (harvest_date);
CREATE INDEX idx_cy_model ON food_security.crop_yields (model_name);
CREATE INDEX idx_cy_bbox ON food_security.crop_yields USING GIST (bbox);

SELECT create_hypertable('food_security.crop_yields', 'prediction_date',
    chunk_time_interval => INTERVAL '3 months',
    if_not_exists => TRUE);

-- --------------------------------------------------------------------------
-- food_security.drought_alerts  –  drought early warning signals
-- --------------------------------------------------------------------------
CREATE TABLE food_security.drought_alerts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    severity VARCHAR(5) NOT NULL,  -- D0–D4 (US Drought Monitor scale)
    bbox GEOMETRY(Polygon, 4326) NOT NULL,
    onset_date TIMESTAMPTZ NOT NULL,
    expected_duration_days INTEGER NOT NULL,
    affected_area_km2 DOUBLE PRECISION NOT NULL,
    soil_moisture_percentile DOUBLE PRECISION,
    precipitation_deficit_mm DOUBLE PRECISION,
    affected_crops TEXT[],
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT valid_severity CHECK (severity IN ('D0','D1','D2','D3','D4'))
);

CREATE INDEX idx_da_severity ON food_security.drought_alerts (severity);
CREATE INDEX idx_da_onset ON food_security.drought_alerts (onset_date);
CREATE INDEX idx_da_bbox ON food_security.drought_alerts USING GIST (bbox);

-- --------------------------------------------------------------------------
-- food_security.food_security_index  –  composite food security scores
-- --------------------------------------------------------------------------
CREATE TABLE food_security.food_security_index (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    bbox GEOMETRY(Polygon, 4326) NOT NULL,
    h3_index VARCHAR(15),
    timestamp TIMESTAMPTZ NOT NULL,
    availability_score DOUBLE PRECISION CHECK (availability_score BETWEEN 0 AND 1),
    access_score DOUBLE PRECISION CHECK (access_score BETWEEN 0 AND 1),
    utilization_score DOUBLE PRECISION CHECK (utilization_score BETWEEN 0 AND 1),
    stability_score DOUBLE PRECISION CHECK (stability_score BETWEEN 0 AND 1),
    overall_score DOUBLE PRECISION CHECK (overall_score BETWEEN 0 AND 1),
    population_affected INTEGER,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_fsi_h3 ON food_security.food_security_index (h3_index);
CREATE INDEX idx_fsi_time ON food_security.food_security_index (timestamp);
CREATE INDEX idx_fsi_overall ON food_security.food_security_index (overall_score);
CREATE INDEX idx_fsi_bbox ON food_security.food_security_index USING GIST (bbox);

SELECT create_hypertable('food_security.food_security_index', 'timestamp',
    chunk_time_interval => INTERVAL '3 months',
    if_not_exists => TRUE);

-- --------------------------------------------------------------------------
-- food_security.crop_landcover  –  CropScape / CDL statistics
-- --------------------------------------------------------------------------
CREATE TABLE food_security.crop_landcover (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    year INTEGER NOT NULL,
    bbox GEOMETRY(Polygon, 4326) NOT NULL,
    h3_index VARCHAR(15),
    crop_code INTEGER NOT NULL,
    crop_name VARCHAR(100) NOT NULL,
    acreage DOUBLE PRECISION NOT NULL,
    percentage DOUBLE PRECISION,
    source VARCHAR(100) DEFAULT 'usda_cropscape',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_cl_year ON food_security.crop_landcover (year);
CREATE INDEX idx_cl_crop ON food_security.crop_landcover (crop_code);
CREATE INDEX idx_cl_h3 ON food_security.crop_landcover (h3_index);
CREATE INDEX idx_cl_bbox ON food_security.crop_landcover USING GIST (bbox);
