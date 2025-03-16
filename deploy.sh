#!/bin/bash
# filepath: deploy.sh

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${YELLOW}=== Deploying Services Using Existing Configuration ===${NC}"

# Check if Docker and Docker Compose are installed
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Docker is not installed. Please install Docker and try again.${NC}"
    exit 1
fi

if ! docker compose version &> /dev/null; then
    echo -e "${RED}Docker Compose is not available. Please install Docker Compose and try again.${NC}"
    exit 1
fi

# Create the shared network if it doesn't exist
echo -e "${YELLOW}Creating shared Docker network 'mod-network' if it doesn't exist...${NC}"
docker network inspect mod-network >/dev/null 2>&1 || docker network create mod-network

# Deploy kafka first (if needed)
echo -e "${YELLOW}Deploying Kafka...${NC}"
cd infrastructure/kafka
docker compose up -d
cd ../..

# Deploy Redis
echo -e "${YELLOW}Deploying Redis...${NC}"
cd infrastructure/redis
docker compose up -d
cd ../..

# Deploy Chat History Service
echo -e "${YELLOW}Deploying Chat History Service...${NC}"
cd chat-history
docker compose up -d
cd ..

# Deploy Orchestrator
echo -e "${YELLOW}Deploying Orchestrator Service...${NC}"
cd orchestrator
docker compose up -d
cd ..

echo -e "${GREEN}Services deployed successfully!${NC}"
echo -e "${GREEN}=== Access Information ===${NC}"
echo -e "Chat History API: http://localhost:8000"
echo -e "Redis: localhost:6379"

# Show current CLI .env content
echo -e "${YELLOW}Current CLI .env configuration:${NC}"
cat frontend/cli/src/cli/.env

echo
echo -e "${YELLOW}Make sure the above configuration is correct for your environment.${NC}"

echo -e "${GREEN}Deployment script finished.${NC}"
echo -e "${YELLOW}To stop all services: ${NC}cd chat-history && docker compose down && cd ../infrastructure/redis && docker compose down"
echo -e "${YELLOW}To view logs: ${NC}cd chat-history && docker compose logs -f"

uv run frontend/cli/src/cli/client.py mod --help