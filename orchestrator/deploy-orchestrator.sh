#!/bin/bash

# Set up colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${YELLOW}=== Deploying Orchestrator with NGINX Reverse Proxy ===${NC}"

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

#=============================================================
# STEP 1: DEPLOY ORCHESTRATOR SERVICE
#=============================================================
echo -e "\n${YELLOW}=== STEP 1: DEPLOYING ORCHESTRATOR SERVICE ===${NC}"

# Build the orchestrator image
echo -e "${YELLOW}Building orchestrator image...${NC}"
docker build -t mod/orchestrator:latest .

# Deploy the orchestrator stack
echo -e "${YELLOW}Deploying orchestrator stack...${NC}"
docker stack deploy -c docker-compose.yml orchestrator

# Check deployment status
echo -e "${YELLOW}Checking orchestrator deployment status...${NC}"
sleep 5
docker stack services orchestrator

# Verify orchestrator service is running
if ! docker service ls | grep -q "orchestrator_orchestrator"; then
    echo -e "${RED}Orchestrator service failed to deploy. Check logs with: docker service logs orchestrator_orchestrator${NC}"
    exit 1
fi

echo -e "${GREEN}Orchestrator service deployed successfully!${NC}"

#=============================================================
# STEP 2: DEPLOY NGINX REVERSE PROXY
#=============================================================
echo -e "\n${YELLOW}=== STEP 2: DEPLOYING NGINX REVERSE PROXY ===${NC}"

# Navigate to the NGINX directory
NGINX_DIR="../infrastructure/nginx"
if [ ! -d "$NGINX_DIR" ]; then
    echo -e "${RED}NGINX directory not found at $NGINX_DIR. Please check the path.${NC}"
    exit 1
fi

# Check if docker-compose.yml needs path adjustment
if grep -q "./infrastructure/nginx/nginx.conf" "$NGINX_DIR/docker-compose.yml"; then
    echo -e "${YELLOW}Fixing paths in NGINX docker-compose.yml...${NC}"
    sed -i 's|./infrastructure/nginx/nginx.conf|./nginx.conf|g' "$NGINX_DIR/docker-compose.yml" || {
        echo -e "${YELLOW}Could not automatically update paths. This might not be an issue.${NC}"
    }
fi

# Deploy NGINX with Docker Stack
echo -e "${YELLOW}Deploying NGINX reverse proxy using Docker Stack...${NC}"
docker stack deploy -c "$NGINX_DIR/docker-compose.yml" nginx-proxy || {
    echo -e "${RED}Failed to deploy NGINX stack. See error above.${NC}"
    exit 1
}

# Wait for the NGINX service to be ready
echo -e "${YELLOW}Waiting for NGINX to be available...${NC}"
sleep 5

# Check if the NGINX service is running
if docker service ls | grep -q "nginx-proxy_nginx"; then
    echo -e "${GREEN}NGINX Reverse Proxy deployed successfully!${NC}"
else
    echo -e "${RED}Something went wrong. The NGINX service is not showing in the service list.${NC}"
    echo -e "${RED}Please check logs with: docker service logs nginx-proxy_nginx${NC}"
    exit 1
fi

#=============================================================
# DEPLOYMENT COMPLETE
#=============================================================
echo -e "\n${GREEN}=== DEPLOYMENT COMPLETE ===${NC}"
echo -e "${GREEN}Orchestrator is now running behind NGINX reverse proxy${NC}"
echo -e "\n${YELLOW}Access Information:${NC}"
echo -e "- NGINX Reverse Proxy: ${GREEN}http://localhost:8000${NC} (Main access point)"
echo -e "- Direct Orchestrator: ${GREEN}http://localhost:8082${NC} (For debugging)"

echo -e "\n${YELLOW}Management Commands:${NC}"
echo -e "- View all services:     ${GREEN}docker service ls${NC}"
echo -e "- Scale orchestrator:    ${GREEN}docker service scale orchestrator_orchestrator=5${NC}"
echo -e "- View orchestrator logs:${GREEN}docker service logs orchestrator_orchestrator${NC}"
echo -e "- View NGINX logs:       ${GREEN}docker service logs nginx-proxy_nginx${NC}"
echo -e "- Remove all:            ${GREEN}docker stack rm orchestrator nginx-proxy${NC}"

echo -e "\n${YELLOW}===================================${NC}"
echo -e "${GREEN}Deployment successful!${NC}"