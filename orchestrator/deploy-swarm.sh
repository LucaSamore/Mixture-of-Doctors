#!/bin/bash

# Set up colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${YELLOW}=== Deploying Orchestrator with Docker Swarm ===${NC}"

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Docker is not installed. Please install Docker and try again.${NC}"
    exit 1
fi

# Initialize Docker Swarm if not already initialized
if ! docker info | grep -q "Swarm: active"; then
    echo -e "${YELLOW}Initializing Docker Swarm...${NC}"
    docker swarm init
    if [ $? -ne 0 ]; then
        echo -e "${RED}Failed to initialize Docker Swarm. Please check the error message above.${NC}"
        exit 1
    fi
    echo -e "${GREEN}Docker Swarm initialized successfully.${NC}"
else
    echo -e "${GREEN}Docker Swarm is already initialized.${NC}"
fi

# Handle network - remove local network and create swarm network
echo -e "${YELLOW}Setting up swarm network...${NC}"

# Check if a local network with this name exists and remove it
if docker network ls --filter name=mod-network --filter scope=local -q | grep -q .; then
    echo -e "${YELLOW}Found local network 'mod-network'. Removing it...${NC}"
    docker network rm mod-network || echo -e "${RED}Failed to remove local network (it may be in use).${NC}"
fi

# Now create a swarm network if it doesn't exist
if ! docker network ls --filter name=mod-network --filter scope=swarm -q | grep -q .; then
    echo -e "${YELLOW}Creating swarm network 'mod-network'...${NC}"
    docker network create --driver overlay --attachable mod-network
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}Network 'mod-network' created in swarm scope.${NC}"
    else
        echo -e "${RED}Failed to create network. Exiting.${NC}"
        exit 1
    fi
else
    echo -e "${GREEN}Swarm network 'mod-network' already exists.${NC}"
fi

# Build the orchestrator image
echo -e "${YELLOW}Building orchestrator image...${NC}"
docker build -t mod/orchestrator:latest .

# Deploy the stack
echo -e "${YELLOW}Deploying orchestrator stack...${NC}"
docker stack deploy -c docker-compose.yml orchestrator

# Check deployment status
echo -e "${YELLOW}Checking deployment status...${NC}"
sleep 5
docker stack services orchestrator

echo -e "${GREEN}=== Orchestrator Deployed with Docker Swarm ===${NC}"
echo -e "Access the service at: http://localhost:8082"
echo
echo -e "${YELLOW}Commands to manage your swarm:${NC}"
echo -e "- View services: ${GREEN}docker service ls${NC}"
echo -e "- Scale services: ${GREEN}docker service scale orchestrator_orchestrator=5${NC}"
echo -e "- View logs: ${GREEN}docker service logs orchestrator_orchestrator${NC}"
echo -e "- Remove stack: ${GREEN}docker stack rm orchestrator${NC}"