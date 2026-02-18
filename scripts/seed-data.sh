#!/bin/bash
set -e

# ANSI color codes
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Seeding EcoTrack Development Database ===${NC}"

# Check if virtual environment is activated
if [[ -z "${VIRTUAL_ENV}" ]]; then
    echo -e "${YELLOW}Virtual environment not activated. Activating...${NC}"
    if [ -d "venv" ]; then
        source venv/bin/activate
        echo -e "${GREEN}✓ Activated virtual environment${NC}"
    else
        echo -e "${RED}Error: Virtual environment not found. Run setup-dev.sh first.${NC}"
        exit 1
    fi
fi

# Load environment variables
if [ -f "configs/development/.env" ]; then
    echo -e "${YELLOW}Loading environment variables from configs/development/.env${NC}"
    export $(grep -v '^#' configs/development/.env | xargs)
else
    echo -e "${YELLOW}Warning: .env file not found. Using default values.${NC}"
    # Set default values
    export DB_HOST=localhost
    export DB_PORT=5432
    export DB_NAME=ecotrack
    export DB_USER=ecotrack
    export DB_PASSWORD=ecotrack_dev
fi

# Check database connection
echo -e "${YELLOW}Checking database connection...${NC}"
if ! PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -U $DB_USER -d $DB_NAME -c '\q' > /dev/null 2>&1; then
    echo -e "${RED}Error: Could not connect to database. Check your database settings.${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Database connection successful${NC}"

# Seed core data
echo -e "${YELLOW}Seeding core data...${NC}"
python -c "
from ecotrack.models.base import Base
from ecotrack.models.geospatial import Region
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import uuid
from shapely.geometry import Polygon
from geoalchemy2.shape import from_shape

# Create database connection
engine = create_engine(f'postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}')
Session = sessionmaker(bind=engine)
session = Session()

# Seed regions
print('Seeding regions...')
regions = [
    Region(
        id=uuid.uuid4(),
        name='San Francisco Bay Area',
        h3_index='832830fffffffff',
        h3_resolution=3,
        geometry=from_shape(Polygon([
            (-122.51, 37.70), (-122.51, 37.85),
            (-122.35, 37.85), (-122.35, 37.70),
            (-122.51, 37.70)
        ]), srid=4326),
        area_km2=1234.56,
        country_iso3='USA',
        admin_level=2,
        properties={'population': 7750000, 'climate_zone': 'Mediterranean'}
    ),
    Region(
        id=uuid.uuid4(),
        name='Greater London',
        h3_index='831c9fffffffff',
        h3_resolution=3,
        geometry=from_shape(Polygon([
            (-0.51, 51.30), (-0.51, 51.70),
            (0.30, 51.70), (0.30, 51.30),
            (-0.51, 51.30)
        ]), srid=4326),
        area_km2=1572.00,
        country_iso3='GBR',
        admin_level=2,
        properties={'population': 8900000, 'climate_zone': 'Oceanic'}
    ),
    Region(
        id=uuid.uuid4(),
        name='Amazon Rainforest (Part)',
        h3_index='84a96fffffffff',
        h3_resolution=3,
        geometry=from_shape(Polygon([
            (-65.00, -5.00), (-65.00, -2.00),
            (-60.00, -2.00), (-60.00, -5.00),
            (-65.00, -5.00)
        ]), srid=4326),
        area_km2=121543.00,
        country_iso3='BRA',
        admin_level=1,
        properties={'ecosystem': 'Tropical rainforest', 'biodiversity_index': 9.8}
    )
]

for region in regions:
    existing = session.query(Region).filter(Region.name == region.name).first()
    if not existing:
        session.add(region)

# Seed data sources
print('Seeding data sources...')
session.execute(text(\"\"\"
INSERT INTO eco_core.data_sources (name, source_type, provider, license, stac_collection_id, config, is_active)
VALUES
    ('ERA5 Hourly', 'api', 'ECMWF CDS', 'CC-BY-4.0', NULL, '{}', TRUE),
    ('Sentinel-2 L2A', 'stac', 'Copernicus Data Space', 'CC-BY-4.0', 'sentinel-2-l2a', '{}', TRUE),
    ('GBIF Occurrences', 'api', 'GBIF', 'CC0', NULL, '{}', TRUE),
    ('OpenAQ', 'api', 'OpenAQ', 'CC-BY-4.0', NULL, '{}', TRUE)
ON CONFLICT (name) DO NOTHING;
\"\"\"))

# Commit changes
session.commit()
session.close()
print('Core data seeded successfully!')
"
echo -e "${GREEN}✓ Core data seeded successfully${NC}"

# Seed climate data
echo -e "${YELLOW}Seeding climate data...${NC}"
python -c "
from sqlalchemy import create_engine, text
import random
from datetime import datetime, timedelta

# Create database connection
engine = create_engine(f'postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}')

# Get regions
regions = []
with engine.connect() as conn:
    result = conn.execute(text('SELECT h3_index FROM eco_core.regions'))
    regions = [row[0] for row in result]

# Seed climate observations
print('Seeding climate observations...')
if regions:
    # Generate sample data for the past 7 days
    now = datetime.now()
    start_date = now - timedelta(days=7)
    
    # Variables to seed
    variables = ['temperature_2m', 'precipitation', 'wind_speed_10m', 'humidity_2m']
    units = {'temperature_2m': 'C', 'precipitation': 'mm', 'wind_speed_10m': 'm/s', 'humidity_2m': '%'}
    
    # Generate values
    values = []
    for region in regions:
        for var in variables:
            for i in range(7*24):  # Hourly data for 7 days
                timestamp = start_date + timedelta(hours=i)
                
                # Generate realistic values
                if var == 'temperature_2m':
                    value = 15 + 10 * random.random() - 5 * random.random()  # 5-25°C
                elif var == 'precipitation':
                    value = 0 if random.random() > 0.3 else 5 * random.random()  # 70% chance of 0, otherwise 0-5mm
                elif var == 'wind_speed_10m':
                    value = 2 + 8 * random.random()  # 2-10 m/s
                else:  # humidity
                    value = 40 + 50 * random.random()  # 40-90%
                
                values.append(f\"('{region}', '{timestamp.isoformat()}', '{var}', {value}, '{units[var]}', 0)\")
    
    # Insert in batches
    batch_size = 1000
    for i in range(0, len(values), batch_size):
        batch = values[i:i+batch_size]
        with engine.connect() as conn:
            conn.execute(text(f\"\"\"
            INSERT INTO eco_climate.observations (h3_index, observed_at, variable, value, unit, quality_flag)
            VALUES {', '.join(batch)}
            ON CONFLICT DO NOTHING;
            \"\"\"))
            conn.commit()

print('Climate data seeded successfully!')
"
echo -e "${GREEN}✓ Climate data seeded successfully${NC}"

# Seed biodiversity data
echo -e "${YELLOW}Seeding biodiversity data...${NC}"
python -c "
from sqlalchemy import create_engine, text
import random
import uuid
from datetime import datetime, timedelta

# Create database connection
engine = create_engine(f'postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}')

# Seed species
print('Seeding species data...')
species = [
    (str(uuid.uuid4()), 'Panthera onca', 'Jaguar', '{\"kingdom\": \"Animalia\", \"phylum\": \"Chordata\", \"class\": \"Mammalia\", \"order\": \"Carnivora\", \"family\": \"Felidae\"}', 'NT', 5037357),
    (str(uuid.uuid4()), 'Ara macao', 'Scarlet Macaw', '{\"kingdom\": \"Animalia\", \"phylum\": \"Chordata\", \"class\": \"Aves\", \"order\": \"Psittaciformes\", \"family\": \"Psittacidae\"}', 'LC', 2479041),
    (str(uuid.uuid4()), 'Ursus arctos', 'Brown Bear', '{\"kingdom\": \"Animalia\", \"phylum\": \"Chordata\", \"class\": \"Mammalia\", \"order\": \"Carnivora\", \"family\": \"Ursidae\"}', 'LC', 2433433),
    (str(uuid.uuid4()), 'Quercus robur', 'English Oak', '{\"kingdom\": \"Plantae\", \"phylum\": \"Tracheophyta\", \"class\": \"Magnoliopsida\", \"order\": \"Fagales\", \"family\": \"Fagaceae\"}', 'LC', 2878688)
]

with engine.connect() as conn:
    for species_data in species:
        conn.execute(text(f\"\"\"
        INSERT INTO eco_biodiversity.species (id, scientific_name, common_name, taxonomy, iucn_status, gbif_taxon_key)
        VALUES ('{species_data[0]}', '{species_data[1]}', '{species_data[2]}', '{species_data[3]}', '{species_data[4]}', {species_data[5]})
        ON CONFLICT (scientific_name) DO NOTHING;
        \"\"\"))
    conn.commit()

print('Biodiversity data seeded successfully!')
"
echo -e "${GREEN}✓ Biodiversity data seeded successfully${NC}"

echo -e "\n${GREEN}=== Database seeding completed successfully! ===${NC}"