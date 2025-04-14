#!/bin/bash

set -e

# Include utility functions
source ./scripts/deploy_utils.sh

# Check if first argument is "ingest" to run ingestion after deployment
RUN_INGESTION=false
if [ "$1" = "--ingest" ]; then
    RUN_INGESTION=true
    echo -e "${YELLOW}=== Will run data ingestion after deployment ===${NC}"
fi

echo -e "${YELLOW}=== Deploying All Services Using Docker Swarm ===${NC}"

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

# Create a shared Docker Swarm network if it doesn't exist
echo -e "${YELLOW}Creating shared Docker Swarm network 'mod-network' if it doesn't exist...${NC}"
if ! docker network ls --filter name=mod-network --filter scope=swarm -q | grep -q .; then
    docker network create --driver overlay --attachable mod-network
    if [ $? -ne 0 ]; then
        echo -e "${RED}Failed to create network. Exiting.${NC}"
        exit 1
    fi
    echo -e "${GREEN}Network 'mod-network' created in swarm scope.${NC}"
else
    echo -e "${GREEN}Swarm network 'mod-network' already exists.${NC}"
fi

# Deploy Kafka with Docker Swarm
cd infrastructure/kafka
deploy_service "kafka" "." ""
cd ../..

# Wait for Kafka to be ready
wait_for_service "kafka_kafka" 30 5 10

# Deploy Redis with Docker Swarm
deploy_service "redis" "infrastructure/redis" ""

# Wait for Redis and Redis Insight to be ready
wait_for_service "redis_redis" 30 5 5
wait_for_service "redis_redis-insight" 30 5 0

echo -e "Creating Redis database in Redis Insight...${NC}"

# API URL for RedisInsight
API_URL="http://localhost:${REDIS_INSIGHT_PORT}/api"
    
EXISTING_DBS=$(curl -s -X GET "${API_URL}/databases" -H "Content-Type: application/json")

# Check if the database exists
if echo "$EXISTING_DBS" | grep -q "\"host\":\"${REDIS_HOST}\"" && \
   echo "$EXISTING_DBS" | grep -q "\"port\":${REDIS_PORT}" && \
   echo "$EXISTING_DBS" | grep -q "\"name\":\"${REDIS_NAME}\""; then
    echo -e "${GREEN}Redis database already exists. Skipping database creation.${NC}"
else
    echo -e "Adding Redis database...${NC}"
    
    # Add the database
    ADD_RESPONSE=$(curl -s -X POST "${API_URL}/databases" \
        -H "Content-Type: application/json" \
        -d "{
            \"host\": \"${REDIS_HOST}\", 
            \"port\": ${REDIS_PORT},
            \"username\": \"${REDIS_USERNAME}\",
            \"password\": \"${REDIS_PASSWORD}\",
            \"name\": \"${REDIS_NAME}\"
        }")
    
    # Check if the addition was successful
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}Successfully added Redis database${NC}"
    else
        echo -e "${RED}Error: Failed to add Redis database${NC}"
        echo -e "${RED}Response: ${ADD_RESPONSE}${NC}"
    fi
fi

# Deploy Chat History with Docker Swarm
deploy_service "chat-history" "chat-history" "mod/chat-history:latest"

echo -e "${GREEN}Waiting for message broker other 20 seconds... ${NC}"
sleep 20

# Deploy Orchestrator with Docker Swarm
deploy_service "orchestrator" "orchestrator" "mod/orchestrator:latest"

# Deploy RAG modules for each domain
echo -e "${YELLOW}=== Deploying RAG modules for each domain ===${NC}"
# Deploy RAG services using the utility function
deploy_rag_services "rag-module"
echo -e "${GREEN}RAG modules deployment completed.${NC}"

# Run ingestion if requested
if [ "$RUN_INGESTION" = true ]; then
    echo -e "${YELLOW}=== Running data ingestion as requested ===${NC}"
    ./scripts/ingest_rag_data.sh
    echo -e "${GREEN}Data ingestion completed.${NC}"
else
    echo -e "${YELLOW}Skipping data ingestion. To run ingestion, use './deploy.sh --ingest'${NC}"
fi

echo -e "${GREEN}Deployment script finished.${NC}"
echo -e "${YELLOW}To stop all services run: ${NC}./undeploy.sh"
echo -e "${YELLOW}To view Docker Swarm services: ${NC}docker service ls"
echo -e "${YELLOW}To view logs for a service: ${NC}docker service logs <service_name>"

# Optionally show CLI help
if command -v uv &> /dev/null; then
    uv run frontend/cli/src/cli/client.py mod --help
fi

# Check deployment status of all services
echo -e "${YELLOW}Checking deployment status of all stacks...${NC}"
sleep 5
echo -e "${YELLOW}=== Services Status ===${NC}"
docker stack ls
echo -e "${YELLOW}=== Detailed Services Status ===${NC}"
docker service ls

echo -e "${GREEN}All services deployed successfully!${NC}"
echo -e "${GREEN}=== Access Information ===${NC}"
echo -e "Kafka UI: http://localhost:8080"
echo -e "MongoDB UI: http://localhost:8081"
echo -e "Orchestrator: http://localhost:8082/docs"
echo -e "Chat History API: http://localhost:8089"
echo -e "Redis UI: http://localhost:5540"
echo -e "Qdrant Dashboards:"
echo -e "http://localhost:6333/dashboard"
echo -e "http://localhost:6343/dashboard"
echo -e "http://localhost:6353/dashboard"

# Show current CLI .env content
echo -e "${YELLOW}Current CLI .env configuration:${NC}"
cat frontend/cli/src/cli/.env 2>/dev/null || echo "No .env file found for CLI"

echo
echo -e "${YELLOW}Make sure the above configuration is correct for your environment.${NC}"