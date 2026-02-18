-- ==========================================================================
-- Migration 003: Biodiversity domain tables
-- ==========================================================================
-- Creates schema and tables for species records, occurrence observations,
-- and ecosystem health indices.
-- ==========================================================================

CREATE SCHEMA IF NOT EXISTS biodiversity;

-- --------------------------------------------------------------------------
-- biodiversity.species  –  canonical species registry
-- --------------------------------------------------------------------------
CREATE TABLE biodiversity.species (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scientific_name VARCHAR(200) UNIQUE NOT NULL,
    common_name VARCHAR(200),
    taxonomic_rank VARCHAR(20) DEFAULT 'species',
    conservation_status VARCHAR(5) DEFAULT 'NE',
    taxonomy JSONB DEFAULT '{}',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_bio_species_name ON biodiversity.species (scientific_name);
CREATE INDEX idx_bio_species_status ON biodiversity.species (conservation_status);
CREATE INDEX idx_bio_species_taxonomy ON biodiversity.species USING GIN (taxonomy);

-- --------------------------------------------------------------------------
-- biodiversity.observations  –  species occurrence records
-- --------------------------------------------------------------------------
CREATE TABLE biodiversity.observations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    species_id UUID REFERENCES biodiversity.species(id),
    species_name VARCHAR(200) NOT NULL,
    location GEOMETRY(Point, 4326) NOT NULL,
    h3_index VARCHAR(15) NOT NULL,
    observed_at TIMESTAMPTZ NOT NULL,
    observer VARCHAR(200),
    count INTEGER DEFAULT 1,
    evidence_type VARCHAR(50) DEFAULT 'human_observation',
    confidence DOUBLE PRECISION DEFAULT 1.0,
    source_dataset VARCHAR(100),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_bio_obs_species ON biodiversity.observations (species_name);
CREATE INDEX idx_bio_obs_h3 ON biodiversity.observations (h3_index);
CREATE INDEX idx_bio_obs_time ON biodiversity.observations (observed_at);
CREATE INDEX idx_bio_obs_location ON biodiversity.observations USING GIST (location);
CREATE INDEX idx_bio_obs_species_id ON biodiversity.observations (species_id);
CREATE INDEX idx_bio_obs_source ON biodiversity.observations (source_dataset);

SELECT create_hypertable('biodiversity.observations', 'observed_at',
    chunk_time_interval => INTERVAL '3 months',
    if_not_exists => TRUE);

-- --------------------------------------------------------------------------
-- biodiversity.ecosystem_health  –  composite health scores per region
-- --------------------------------------------------------------------------
CREATE TABLE biodiversity.ecosystem_health (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    bbox GEOMETRY(Polygon, 4326) NOT NULL,
    h3_index VARCHAR(15),
    timestamp TIMESTAMPTZ NOT NULL,
    species_richness_score DOUBLE PRECISION CHECK (species_richness_score BETWEEN 0 AND 1),
    habitat_integrity_score DOUBLE PRECISION CHECK (habitat_integrity_score BETWEEN 0 AND 1),
    connectivity_score DOUBLE PRECISION CHECK (connectivity_score BETWEEN 0 AND 1),
    threat_level_score DOUBLE PRECISION CHECK (threat_level_score BETWEEN 0 AND 1),
    overall_score DOUBLE PRECISION CHECK (overall_score BETWEEN 0 AND 1),
    trend VARCHAR(20) DEFAULT 'stable',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_bio_health_h3 ON biodiversity.ecosystem_health (h3_index);
CREATE INDEX idx_bio_health_time ON biodiversity.ecosystem_health (timestamp);
CREATE INDEX idx_bio_health_bbox ON biodiversity.ecosystem_health USING GIST (bbox);
CREATE INDEX idx_bio_health_trend ON biodiversity.ecosystem_health (trend);

SELECT create_hypertable('biodiversity.ecosystem_health', 'timestamp',
    chunk_time_interval => INTERVAL '3 months',
    if_not_exists => TRUE);
