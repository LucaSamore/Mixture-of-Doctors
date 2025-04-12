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

# Deploy RAG services for each domain in config.json
deploy_rag_services() {
    local rag_module_dir=$1
    
    echo -e "${YELLOW}Deploying RAG modules for each domain...${NC}"
    
    # Extract available domains from config.json
    DOMAINS=$(grep -o '"[^"]*"' "config.json" | grep -v "rag_modules" | tr -d '"' | grep -v '[{}]')
    
    echo -e "${GREEN}Found domains: $DOMAINS${NC}"
    
    # Change to the rag-module directory where docker-compose.yml is located
    cd "$rag_module_dir"
    
    # Build the RAG module image once (will be used by all domains)
    echo -e "${YELLOW}Building RAG module image...${NC}"
    docker build -t mixture-of-doctors/rag-module:latest .
    
    # Base port for REST API (will be incremented for each domain)
    BASE_REST_PORT=6333
    # Base port for gRPC API (will be incremented for each domain)
    BASE_GRPC_PORT=6334
    
    # Loop through domains and start a RAG container for each with its own Qdrant
    domain_index=0
    for domain in $DOMAINS; do
        echo -e "${YELLOW}Starting RAG module with domain: $domain${NC}"
        
        # Calculate ports for this domain (incrementing by 10 to avoid conflicts)
        QDRANT_REST_PORT=$((BASE_REST_PORT + (domain_index * 10)))
        QDRANT_GRPC_PORT=$((BASE_GRPC_PORT + (domain_index * 10)))
        
        # Define unique stack name for each domain
        stack_name="rag-$domain"
        
        # Export environment variables for docker-compose
        export RAG_DOMAIN=$domain
        export QDRANT_REST_PORT=$QDRANT_REST_PORT
        export QDRANT_GRPC_PORT=$QDRANT_GRPC_PORT
        
        # Process docker-compose with environment variables
        envsubst < docker-compose.yml > docker-compose-processed.yml
        
        # Deploy using docker stack instead of docker-compose
        docker stack deploy -c docker-compose-processed.yml $stack_name
        
        echo -e "${GREEN}Started $stack_name with Qdrant on port $QDRANT_REST_PORT${NC}"
        echo -e "${GREEN}Qdrant dashboard for $domain available at: http://localhost:$QDRANT_REST_PORT/dashboard${NC}"
        
        # Increment domain index for next iteration
        domain_index=$((domain_index + 1))
        
        # Short pause to avoid simultaneous startup issues
        sleep 1
        
        # Clean up processed file
        rm docker-compose-processed.yml
    done
    
    echo -e "${GREEN}All RAG modules deployed!${NC}"
    echo -e "${GREEN}Check above for the specific Qdrant dashboard URLs for each domain${NC}"
    
    # Return to original directory
    cd - > /dev/null
}

# Function to remove a stack and wait for it to be fully removed
remove_stack() {
    local stack_name=$1
    
    if docker stack ls | grep -q "^$stack_name "; then
        echo -e "${YELLOW}Removing $stack_name stack...${NC}"
        docker stack rm $stack_name
        
        # Wait for all services to be removed
        echo -e "${YELLOW}Waiting for $stack_name services to be completely removed...${NC}"
        while docker service ls --filter name=$stack_name -q | grep -q .; do
            echo -n "."
            sleep 2
        done
        echo -e "\n${GREEN}All $stack_name services removed${NC}"
    else
        echo -e "${YELLOW}Stack $stack_name not found, skipping...${NC}"
    fi
}

# Export the functions
export -f deploy_service
export -f wait_for_service
export -f deploy_rag_services
export -f remove_stack