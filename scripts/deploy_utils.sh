#!/bin/bash

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Function to deploy a service using Docker Swarm with environment variables substitution
deploy_service() {
    local service_name=$1
    local service_dir=$2
    local image_name=$3  # Optional parameter for building image first
    
    echo -e "${YELLOW}Deploying ${service_name} Stack...${NC}"
    cd ${service_dir}
    
    # Build image if specified
    if [ ! -z "$image_name" ]; then
        echo -e "${YELLOW}Building ${service_name} image...${NC}"
        docker build -t ${image_name} .
    fi
    
    # Load environment variables if .env exists
    if [ -f ".env" ]; then
        echo -e "${GREEN}Loading environment variables from .env file${NC}"
        set -a  # automatically export all variables
        source .env
        set +a
    fi
    
    # Use a temporary file to avoid pipe issues
    echo -e "${GREEN}Processing docker-compose.yml with environment variables${NC}"
    envsubst < docker-compose.yml > docker-compose-processed.yml
    
    # Check if processing was successful
    if [ -s "docker-compose-processed.yml" ]; then
        echo -e "${GREEN}Deploying ${service_name} stack with processed configuration${NC}"
        docker stack deploy -c docker-compose-processed.yml ${service_name}
        rm docker-compose-processed.yml  # Clean up temporary file
    else
        echo -e "${RED}Error: Environment variable substitution failed${NC}"
        exit 1
    fi
    cd - > /dev/null
}

# Wait for a service to be ready
wait_for_service() {
    local service_name=$1
    local max_attempts=${2:-30}
    local sleep_time=${3:-5}
    local extra_sleep=${4:-0}
    
    echo -e "${YELLOW}Waiting for ${service_name} to become ready...${NC}"
    local attempt=0
    
    while [ $attempt -lt $max_attempts ]; do
        if docker service ls --filter "name=${service_name}" --format "{{.Replicas}}" | grep -q "[1-9]/[1-9]"; then
            echo -e "${GREEN}${service_name} service is running!${NC}"
            if [ $extra_sleep -gt 0 ]; then
                echo -e "${YELLOW}Waiting ${extra_sleep} more seconds for service to stabilize...${NC}"
                sleep $extra_sleep
            fi
            return 0
        fi
        
        attempt=$((attempt+1))
        echo -e "${YELLOW}Waiting for ${service_name} to start... ($attempt/$max_attempts)${NC}"
        sleep $sleep_time
        
        if [ $attempt -eq $max_attempts ]; then
            echo -e "${RED}Timeout waiting for ${service_name}. Check logs with 'docker service logs ${service_name}'${NC}"
            return 1
        fi
    done
}

# Export the functions
export -f deploy_service
export -f wait_for_service