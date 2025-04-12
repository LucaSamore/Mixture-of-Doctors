#!/bin/bash

# Get the root path of the project
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RAG_MODULE_DIR="${ROOT_DIR}/rag-module"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if config.json exists in the root directory
if [ ! -f "$ROOT_DIR/config.json" ]; then
    echo -e "${RED}Error: config.json not found in the root directory!${NC}"
    exit 1
fi

# Import the utility functions
source "${ROOT_DIR}/scripts/deploy_utils.sh"

# Extract available domains from config.json
DOMAINS=$(grep -o '"[^"]*"' "$ROOT_DIR/config.json" | grep -v "rag_modules" | tr -d '"' | grep -v '[{}]')

echo -e "${GREEN}Found domains: $DOMAINS${NC}"

# Base port for REST API (will be incremented for each domain)
BASE_REST_PORT=6333

echo -e "${YELLOW}Starting data ingestion for each domain...${NC}"

# First, wait for all RAG services to be fully operational
domain_index=0
for domain in $DOMAINS; do
    echo -e "${YELLOW}Checking if RAG service for domain '${domain}' is ready...${NC}"
    
    # Define unique stack name for each domain
    stack_name="rag-$domain"
    
    # Wait for the entire stack service to be ready using the deploy_utils function
    # Parameters: service_name, max_attempts, sleep_time, extra_sleep
    echo -e "${YELLOW}Waiting for ${stack_name}_qdrant service to be available...${NC}"
    if ! docker service ls | grep -q "${stack_name}_qdrant"; then
        echo -e "${RED}ERROR: The ${stack_name}_qdrant service does not exist!${NC}"
        echo -e "${RED}Please make sure you've deployed all RAG services using deploy.sh first.${NC}"
        exit 1
    fi

    # Use the wait_for_service function from deploy_utils.sh
    wait_for_service "${stack_name}_qdrant" 30 5 5
    
    # Check the actual connection to the Qdrant REST API
    QDRANT_REST_PORT=$((BASE_REST_PORT + (domain_index * 10)))
    echo -e "${YELLOW}Testing connection to Qdrant API at localhost:${QDRANT_REST_PORT}...${NC}"
    
    # Try to connect to the Qdrant API
    MAX_API_CHECK=10
    for attempt in $(seq 1 $MAX_API_CHECK); do
        echo -e "${YELLOW}API connection attempt ${attempt}/${MAX_API_CHECK}...${NC}"
        if curl -s --connect-timeout 5 "http://localhost:${QDRANT_REST_PORT}/collections" > /dev/null; then
            echo -e "${GREEN}Successfully connected to Qdrant API for domain '${domain}'!${NC}"
            break
        fi
        
        if [ $attempt -eq $MAX_API_CHECK ]; then
            echo -e "${RED}WARNING: Cannot connect to Qdrant API at localhost:${QDRANT_REST_PORT}.${NC}"
            echo -e "${RED}Ingestion for domain '${domain}' may fail. Continuing anyway...${NC}"
        fi
        
        echo -e "${YELLOW}Waiting 5 seconds before retrying...${NC}"
        sleep 5
    done
    
    # Increment domain index for the next domain
    domain_index=$((domain_index + 1))
done

echo -e "${GREEN}All RAG services checked. Proceeding with ingestion...${NC}"

# Delete points from Qdrant collections if they exist
domain_index=0
for domain in $DOMAINS; do
    echo -e "${YELLOW}Processing domain: $domain${NC}"
    QDRANT_REST_PORT=$((BASE_REST_PORT + (domain_index * 10)))
    
    # First check if the collection exists
    COLLECTION_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:$QDRANT_REST_PORT/collections/${domain}_docs")
    
    if [ "$COLLECTION_STATUS" = "200" ]; then
        echo -e "${YELLOW}Deleting all points in the Qdrant collection for domain: $domain${NC}"
        DELETE_RESPONSE=$(curl -s -X POST "http://localhost:$QDRANT_REST_PORT/collections/${domain}_docs/points/delete" \
            -H "Content-Type: application/json" \
            -d '{"filter": {}}')
            
        if echo "$DELETE_RESPONSE" | grep -q "error"; then
            echo -e "${RED}Warning: Issue deleting points for domain $domain: $DELETE_RESPONSE${NC}"
            # Continue anyway, don't exit
        else
            echo -e "${GREEN}All points deleted for domain: $domain${NC}"
        fi
    else
        echo -e "${YELLOW}Collection ${domain}_docs does not exist yet, no need to delete points${NC}"
    fi

    # Increment domain index for the next domain
    domain_index=$((domain_index + 1))
done

# Install dependencies for ingestion script
echo -e "${GREEN}Installing required dependencies for ingestion...${NC}"
cd "$RAG_MODULE_DIR/scripts/"
pip install -r requirements.txt

# Run ingestion for each domain
domain_index=0
for domain in $DOMAINS; do
    echo -e "${GREEN}Running ingestion for domain: $domain${NC}"
    QDRANT_REST_PORT=$((BASE_REST_PORT + (domain_index * 10)))
    python ingest_pubmed.py --domain $domain --query "$domain disease" --count 10 --port $QDRANT_REST_PORT
    
    if [ $? -ne 0 ]; then
        echo -e "${RED}Warning: Issue running ingestion for domain $domain${NC}"
        # Continue with next domain
    else
        echo -e "${GREEN}Ingestion completed for domain: $domain${NC}"
    fi
    
    # Increment domain index for the next domain
    domain_index=$((domain_index + 1))
done

echo -e "${GREEN}Ingestion complete for all domains!${NC}"