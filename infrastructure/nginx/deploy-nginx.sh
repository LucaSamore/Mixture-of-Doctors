#!/bin/bash

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${YELLOW}=== Deploying NGINX Reverse Proxy for Orchestrator ===${NC}"

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}Docker is not running or requires elevated permissions. Please start Docker and try again.${NC}"
    exit 1
fi

# Check if mod-network exists, create if not
if ! docker network inspect mod-network >/dev/null 2>&1; then
    echo -e "${YELLOW}Creating mod-network...${NC}"
    docker network create --driver overlay --attachable mod-network || {
        echo -e "${RED}Failed to create mod-network. Please check your Docker permissions.${NC}"
        exit 1
    }
    echo -e "${GREEN}Network 'mod-network' created successfully.${NC}"
else
    echo -e "${GREEN}Network 'mod-network' already exists.${NC}"
fi

# Fix path in docker-compose.yml if needed
# The docker-compose file references ./infrastructure/nginx/nginx.conf
# which might not be correct if we're executing from inside the nginx folder
cd $(dirname "$0") # Move to the script's directory
CURRENT_DIR=$(pwd)
EXPECTED_PATH="infrastructure/nginx"

if [[ "$CURRENT_DIR" == *"$EXPECTED_PATH" ]]; then
    echo -e "${YELLOW}Checking volume paths in docker-compose.yml...${NC}"
    if grep -q "./infrastructure/nginx/nginx.conf" docker-compose.yml; then
        echo -e "${YELLOW}Updating volume path in docker-compose.yml...${NC}"
        sed -i 's|./infrastructure/nginx/nginx.conf|./nginx.conf|g' docker-compose.yml || {
            echo -e "${YELLOW}Could not automatically update paths. This might not be an issue.${NC}"
        }
    fi
fi

# Deploy with Docker Stack
echo -e "${YELLOW}Deploying NGINX reverse proxy using Docker Stack...${NC}"
docker stack deploy -c docker-compose.yml nginx-proxy || {
    echo -e "${RED}Failed to deploy NGINX stack. See error above.${NC}"
    exit 1
}

# Wait for the service to be ready
echo -e "${YELLOW}Waiting for NGINX to be available...${NC}"
sleep 5

# Check if the service is running
if docker service ls | grep -q "nginx-proxy_nginx"; then
    echo -e "${GREEN}=== NGINX Reverse Proxy Successfully Deployed! ===${NC}"
    echo -e "${GREEN}The reverse proxy is now running and will route requests to the orchestrator service.${NC}"
    echo -e "${GREEN}Access the service at: ${NC}http://localhost:8000"
    echo
    echo -e "${YELLOW}Commands to manage your proxy:${NC}"
    echo -e "  - View service status: ${GREEN}docker service ls${NC}"
    echo -e "  - View service logs: ${GREEN}docker service logs nginx-proxy_nginx${NC}"
    echo -e "  - Remove the proxy: ${GREEN}docker stack rm nginx-proxy${NC}"
else
    echo -e "${RED}Something went wrong. The NGINX service is not showing in the service list.${NC}"
    echo -e "${RED}Please check logs with: docker service logs nginx-proxy_nginx${NC}"
    exit 1
fi