#!/bin/bash
# filepath: c:\dev\code\mixture-of-doctors\undeploy.sh

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if Docker and Docker Compose are installed
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Docker is not installed.${NC}"
    exit 1
fi

if ! docker compose version &> /dev/null; then
    echo -e "${RED}Docker Compose is not available.${NC}"
    exit 1
fi

# Parse command line arguments
REMOVE_VOLUMES=false
if [ "$1" == "--volumes" ] || [ "$1" == "-v" ]; then
    REMOVE_VOLUMES=true
    echo -e "${YELLOW}WARNING: Will remove all volumes (data will be lost)${NC}"
fi

echo -e "${YELLOW}=== Starting un-deployment of all services ===${NC}"

# Function to stop services in a directory
stop_service() {
    local dir=$1
    local service=$2
    
    if [ -f "${dir}/docker-compose.yml" ]; then
        echo -e "${YELLOW}Stopping ${service}...${NC}"
        cd $dir
        if [ "$REMOVE_VOLUMES" = true ]; then
            docker compose down -v
        else
            docker compose down
        fi
        cd - > /dev/null
        echo -e "${GREEN}✓ ${service} stopped${NC}"
    else
        echo -e "${YELLOW}No docker-compose.yml found in ${dir}, skipping...${NC}"
    fi
}

# Remove Docker Swarm stack first
echo -e "${YELLOW}Stopping Orchestrator Docker Swarm stack...${NC}"
if docker stack ls --format "{{.Name}}" | grep -q "^orchestrator$"; then
    docker stack rm orchestrator
    echo -e "${GREEN}✓ Orchestrator stack removed${NC}"
    
    # Wait for services to be fully removed
    echo -e "${YELLOW}Waiting for orchestrator services to be removed...${NC}"
    while docker service ls --filter name=orchestrator -q | grep -q .; do
        sleep 2
    done
else
    echo -e "${YELLOW}Orchestrator stack not found, skipping...${NC}"
fi

# Stop services in reverse order of deployment

# Stop orchestrator
stop_service "orchestrator" "Orchestrator"

# Stop Chat History
stop_service "chat-history" "Chat History"

# Stop Redis
stop_service "infrastructure/redis" "Redis"

# Stop Kafka
stop_service "infrastructure/kafka" "Kafka"

# Remove the shared network
echo -e "${YELLOW}Checking if mod-network is still in use...${NC}"
# Get container count using the network
CONTAINER_COUNT=$(docker network inspect mod-network -f '{{len .Containers}}' 2>/dev/null || echo "0")

if [ "$CONTAINER_COUNT" -eq "0" ]; then
    echo -e "${YELLOW}Removing mod-network...${NC}"
    docker network rm mod-network 2>/dev/null || echo -e "${YELLOW}Network mod-network already removed or doesn't exist${NC}"
else
    echo -e "${YELLOW}Network mod-network still in use by ${CONTAINER_COUNT} containers. Skipping removal.${NC}"
fi

echo -e "${GREEN}=== Un-deployment completed! ===${NC}"

if [ "$REMOVE_VOLUMES" != true ]; then
    echo -e "${YELLOW}Note: Data volumes were preserved. Use './undeploy.sh --volumes' to remove all data.${NC}"
fi