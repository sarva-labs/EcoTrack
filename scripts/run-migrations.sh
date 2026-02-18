#!/bin/bash
set -e

# ANSI color codes
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Running EcoTrack Database Migrations ===${NC}"

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

# Run migrations using Alembic
echo -e "${YELLOW}Running migrations...${NC}"
cd packages/core
alembic upgrade head
echo -e "${GREEN}✓ Core schema migrations completed${NC}"

# Run domain-specific migrations
for domain in climate biodiversity health food equity; do
    echo -e "${YELLOW}Running migrations for $domain domain...${NC}"
    PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -U $DB_USER -d $DB_NAME -c "CREATE SCHEMA IF NOT EXISTS eco_$domain;"
    echo -e "${GREEN}✓ Created schema eco_$domain${NC}"
done

# Create extensions if they don't exist
echo -e "${YELLOW}Setting up PostgreSQL extensions...${NC}"
PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -U $DB_USER -d $DB_NAME -c "CREATE EXTENSION IF NOT EXISTS postgis;"
PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -U $DB_USER -d $DB_NAME -c "CREATE EXTENSION IF NOT EXISTS timescaledb;"
PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -U $DB_USER -d $DB_NAME -c "CREATE EXTENSION IF NOT EXISTS pgvector;"
echo -e "${GREEN}✓ PostgreSQL extensions installed${NC}"

echo -e "\n${GREEN}=== Database migrations completed successfully! ===${NC}"