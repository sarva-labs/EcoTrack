-- ==========================================================================
-- Migration 002: Climate domain tables
-- ==========================================================================
-- Creates schema and tables for climate observations, anomalies, and
-- forecasts.  Uses PostGIS for spatial indexing and TimescaleDB for
-- time-series optimisation.
-- ==========================================================================

CREATE SCHEMA IF NOT EXISTS climate;

-- --------------------------------------------------------------------------
-- climate.observations  –  individual climate measurements
-- --------------------------------------------------------------------------
CREATE TABLE climate.observations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    variable VARCHAR(50) NOT NULL,
    value DOUBLE PRECISION NOT NULL,
    unit VARCHAR(20) NOT NULL,
    location GEOMETRY(Point, 4326) NOT NULL,
    h3_index VARCHAR(15) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    source VARCHAR(100) NOT NULL,
    quality_flag INTEGER DEFAULT 0,
    uncertainty DOUBLE PRECISION,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT valid_quality CHECK (quality_flag BETWEEN 0 AND 9)
);

CREATE INDEX idx_climate_obs_h3 ON climate.observations (h3_index);
CREATE INDEX idx_climate_obs_time ON climate.observations (timestamp);
CREATE INDEX idx_climate_obs_variable ON climate.observations (variable);
CREATE INDEX idx_climate_obs_location ON climate.observations USING GIST (location);

-- TimescaleDB hypertable for time-series optimization
SELECT create_hypertable('climate.observations', 'timestamp',
    chunk_time_interval => INTERVAL '1 month',
    if_not_exists => TRUE);

-- --------------------------------------------------------------------------
-- climate.anomalies  –  detected climate anomalies
-- --------------------------------------------------------------------------
CREATE TABLE climate.anomalies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    variable VARCHAR(50) NOT NULL,
    severity VARCHAR(20) NOT NULL,
    bbox GEOMETRY(Polygon, 4326) NOT NULL,
    detected_at TIMESTAMPTZ NOT NULL,
    baseline_mean DOUBLE PRECISION NOT NULL,
    observed_value DOUBLE PRECISION NOT NULL,
    deviation_sigma DOUBLE PRECISION NOT NULL,
    description TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_climate_anomaly_time ON climate.anomalies (detected_at);
CREATE INDEX idx_climate_anomaly_variable ON climate.anomalies (variable);
CREATE INDEX idx_climate_anomaly_severity ON climate.anomalies (severity);
CREATE INDEX idx_climate_anomaly_bbox ON climate.anomalies USING GIST (bbox);

-- --------------------------------------------------------------------------
-- climate.forecasts  –  model-generated predictions
-- --------------------------------------------------------------------------
CREATE TABLE climate.forecasts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    variable VARCHAR(50) NOT NULL,
    bbox GEOMETRY(Polygon, 4326) NOT NULL,
    forecast_time TIMESTAMPTZ NOT NULL,
    lead_hours INTEGER NOT NULL,
    predicted_value DOUBLE PRECISION NOT NULL,
    prediction_interval_lower DOUBLE PRECISION NOT NULL,
    prediction_interval_upper DOUBLE PRECISION NOT NULL,
    model_name VARCHAR(100) NOT NULL,
    confidence DOUBLE PRECISION CHECK (confidence BETWEEN 0 AND 1),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_climate_fc_time ON climate.forecasts (forecast_time);
CREATE INDEX idx_climate_fc_model ON climate.forecasts (model_name);
CREATE INDEX idx_climate_fc_bbox ON climate.forecasts USING GIST (bbox);

SELECT create_hypertable('climate.forecasts', 'forecast_time',
    chunk_time_interval => INTERVAL '1 week',
    if_not_exists => TRUE);
