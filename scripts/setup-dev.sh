#!/bin/bash
set -e

# ANSI color codes
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== EcoTrack Development Environment Setup ===${NC}"

# Check prerequisites
echo -e "\n${YELLOW}Checking prerequisites...${NC}"

# Check Python version
python_version=$(python3 --version 2>&1 | awk '{print $2}')
python_major=$(echo $python_version | cut -d. -f1)
python_minor=$(echo $python_version | cut -d. -f2)

if [[ $python_major -lt 3 || ($python_major -eq 3 && $python_minor -lt 11) ]]; then
    echo -e "${RED}Error: Python 3.11+ is required. Found Python $python_version${NC}"
    exit 1
else
    echo -e "${GREEN}✓ Python $python_version${NC}"
fi

# Check Node.js version
if command -v node &> /dev/null; then
    node_version=$(node --version | cut -d 'v' -f 2)
    node_major=$(echo $node_version | cut -d. -f1)
    
    if [[ $node_major -lt 20 ]]; then
        echo -e "${RED}Error: Node.js 20+ is required. Found Node.js $node_version${NC}"
        exit 1
    else
        echo -e "${GREEN}✓ Node.js $node_version${NC}"
    fi
else
    echo -e "${RED}Error: Node.js is not installed${NC}"
    exit 1
fi

# Check Docker
if command -v docker &> /dev/null; then
    docker_version=$(docker --version | awk '{print $3}' | sed 's/,//')
    echo -e "${GREEN}✓ Docker $docker_version${NC}"
else
    echo -e "${RED}Error: Docker is not installed${NC}"
    exit 1
fi

# Check Docker Compose
if command -v docker-compose &> /dev/null; then
    docker_compose_version=$(docker-compose --version | awk '{print $3}' | sed 's/,//')
    echo -e "${GREEN}✓ Docker Compose $docker_compose_version${NC}"
else
    echo -e "${YELLOW}Warning: Docker Compose not found as standalone command. This is normal if using Docker Compose V2 integrated with Docker CLI.${NC}"
fi

# Create Python virtual environment
echo -e "\n${YELLOW}Setting up Python virtual environment...${NC}"
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo -e "${GREEN}✓ Created virtual environment${NC}"
else
    echo -e "${YELLOW}Virtual environment already exists${NC}"
fi

# Activate virtual environment
source venv/bin/activate
echo -e "${GREEN}✓ Activated virtual environment${NC}"

# Install Python packages in development mode
echo -e "\n${YELLOW}Installing Python packages...${NC}"
pip install --upgrade pip
echo -e "${GREEN}✓ Upgraded pip${NC}"

# Install core package and dependencies
echo -e "\n${YELLOW}Installing core package...${NC}"
pip install -e "packages/core[dev]"
echo -e "${GREEN}✓ Installed core package${NC}"

# Install other packages
echo -e "\n${YELLOW}Installing other packages...${NC}"
pip install -e packages/geo
pip install -e packages/data-pipeline
pip install -e packages/ml
pip install -e packages/knowledge-graph
pip install -e packages/agents
pip install -e packages/causal
pip install -e packages/rl-policy
pip install -e packages/federated
echo -e "${GREEN}✓ Installed shared packages${NC}"

# Install application packages
echo -e "\n${YELLOW}Installing application packages...${NC}"
pip install -e apps/api-python
pip install -e apps/worker
pip install -e apps/cli
echo -e "${GREEN}✓ Installed application packages${NC}"

# Install Node.js dependencies
echo -e "\n${YELLOW}Installing Node.js dependencies...${NC}"
npm ci
echo -e "${GREEN}✓ Installed Node.js dependencies${NC}"

# Start Docker Compose services
echo -e "\n${YELLOW}Starting Docker Compose services...${NC}"
docker-compose up -d postgres redis minio neo4j
echo -e "${GREEN}✓ Started database services${NC}"

# Wait for PostgreSQL to be ready
echo -e "\n${YELLOW}Waiting for PostgreSQL to be ready...${NC}"
for i in {1..30}; do
    if docker-compose exec postgres pg_isready -U ecotrack > /dev/null 2>&1; then
        echo -e "${GREEN}✓ PostgreSQL is ready${NC}"
        break
    fi
    echo -n "."
    sleep 1
    
    if [ $i -eq 30 ]; then
        echo -e "\n${RED}Error: PostgreSQL did not become ready in time${NC}"
        exit 1
    fi
done

# Run database migrations
echo -e "\n${YELLOW}Running database migrations...${NC}"
./scripts/run-migrations.sh
echo -e "${GREEN}✓ Database migrations completed${NC}"

# Create MinIO buckets
echo -e "\n${YELLOW}Setting up MinIO buckets...${NC}"
docker-compose exec -T minio mkdir -p /data/ecotrack-dev
echo -e "${GREEN}✓ Created MinIO buckets${NC}"

echo -e "\n${GREEN}=== Development environment setup complete! ===${NC}"
echo -e "\n${BLUE}To start the development servers:${NC}"
echo -e "  • API:     ${YELLOW}cd apps/api-python && uvicorn ecotrack_api.main:app --reload${NC}"
echo -e "  • Web:     ${YELLOW}cd apps/web && npm run dev${NC}"
echo -e "  • Worker:  ${YELLOW}cd apps/worker && python -m ecotrack_worker.main${NC}"
echo -e "\n${BLUE}To activate the virtual environment:${NC}"
echo -e "  ${YELLOW}source venv/bin/activate${NC}"
echo -e "\n${BLUE}To view logs:${NC}"
echo -e "  ${YELLOW}docker-compose logs -f${NC}"