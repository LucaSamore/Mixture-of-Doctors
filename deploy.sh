#!/bin/bash

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

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

# Create init-scripts directory if it doesn't exist
mkdir -p init-scripts

# Check if the create-topics.sh script exists, if not create it
if [ ! -f "init-scripts/create-topics.sh" ]; then
    echo "Creating topics initialization script..."
    cat > init-scripts/create-topics.sh << 'EOF'
#!/bin/bash

# Script to create initial Kafka topics
echo "Waiting for Kafka to become ready..."

# Wait for Kafka to be ready
until kafka-topics.sh --bootstrap-server kafka:9092 --list > /dev/null 2>&1; do
  echo "Kafka not yet ready... waiting 5 seconds"
  sleep 5
done

echo "Kafka is ready! Creating topics..."

# Parse config.json to extract RAG module names
if [ -f "/app/config.json" ]; then
  echo "Parsing config.json directly..."
  if grep -q "rag_modules" /app/config.json; then
    # Extract string between square brackets
    RAG_MODULES_STRING=$(grep -o '"rag_modules": \[[^]]*\]' /app/config.json | sed 's/"rag_modules": \[\(.*\)\]/\1/')
    # Convert to array by splitting on commas and removing quotes
    RAG_MODULES=$(echo $RAG_MODULES_STRING | sed 's/"//g' | sed 's/,/ /g')
    
    if [ -z "$RAG_MODULES" ]; then
      echo "No RAG modules found in config. Creating default topic."
      RAG_MODULES="default"
    else
      echo "Found modules: $RAG_MODULES"
    fi
  else
    echo "Config doesn't contain rag_modules key. Creating default topic."
    RAG_MODULES="default"
  fi
else
  echo "Config file not found. Creating default topic."
  RAG_MODULES="default"
fi

# Create topics for each RAG module
for module in $RAG_MODULES; do
  if [ "$module" = "default" ]; then
    TOPIC="rag-module"
  else
    TOPIC="rag-module-$module"
  fi
  
  echo "Creating Kafka topic: $TOPIC"
  kafka-topics.sh --bootstrap-server kafka:9092 --create --if-not-exists \
    --topic $TOPIC \
    --partitions 1 \
    --replication-factor 1
    
  echo "Topic $TOPIC created successfully"
done

# List created topics
echo "Topics created successfully! Current topics:"
kafka-topics.sh --bootstrap-server kafka:9092 --list

echo "Topic initialization complete!"
EOF
    chmod +x init-scripts/create-topics.sh
    echo "Created topic initialization script."
fi

# Deploy Kafka with Docker Swarm
echo -e "${YELLOW}Deploying Kafka Stack...${NC}"
cd infrastructure/kafka
# Ensure config.json is available to the stack
cp ../../config.json ./config.json
export $(grep -v '^#' .env | xargs) 
# docker stack deploy -c docker-compose.yml kafka
envsubst < docker-compose.yml | docker stack deploy -c - kafka
cd ../..

# Wait for Kafka to be ready
echo -e "${YELLOW}Waiting for Kafka to become ready...${NC}"
MAX_ATTEMPTS=30
ATTEMPT=0

while [ $ATTEMPT -lt $MAX_ATTEMPTS ]; do
    if docker service ls --filter "name=kafka_kafka" --format "{{.Replicas}}" | grep -q "[1-9]/[1-9]"; then
        echo -e "${GREEN}Kafka service is running!${NC}"
        sleep 10  # Give it a bit more time to be fully operational
        break
    fi
    
    ATTEMPT=$((ATTEMPT+1))
    echo -e "${YELLOW}Waiting for Kafka to start... ($ATTEMPT/$MAX_ATTEMPTS)${NC}"
    sleep 5
    
    if [ $ATTEMPT -eq $MAX_ATTEMPTS ]; then
        echo -e "${RED}Timeout waiting for Kafka. Check logs with 'docker service logs kafka_kafka'${NC}"
        exit 1
    fi
done

# Deploy Redis with Docker Swarm
echo -e "${YELLOW}Deploying Redis Stack...${NC}"
cd infrastructure/redis
export $(grep -v '^#' .env | xargs)
# docker stack deploy -c docker-compose.yml redis
envsubst < docker-compose.yml | docker stack deploy -c - redis
cd ../..

# Wait for Redis to be ready
echo -e "${YELLOW}Waiting for Redis to become ready...${NC}"
ATTEMPT=0

while [ $ATTEMPT -lt $MAX_ATTEMPTS ]; do
    if docker service ls --filter "name=redis_redis" --format "{{.Replicas}}" | grep -q "[1-9]/[1-9]"; then
        echo -e "${GREEN}Redis service is running!${NC}"
        sleep 5  # Give it a bit more time to be fully operational
        break
    fi
    
    ATTEMPT=$((ATTEMPT+1))
    echo -e "${YELLOW}Waiting for Redis to start... ($ATTEMPT/$MAX_ATTEMPTS)${NC}"
    sleep 5
    
    if [ $ATTEMPT -eq $MAX_ATTEMPTS ]; then
        echo -e "${RED}Timeout waiting for Redis. Check logs with 'docker service logs redis_redis'${NC}"
        exit 1
    fi
done

echo -e "${YELLOW}Waiting for Redis Insight to become ready...${NC}"
ATTEMPT=0

while [ $ATTEMPT -lt $MAX_ATTEMPTS ]; do
    if docker service ls --filter "name=redis_redis-insight" --format "{{.Replicas}}" | grep -q "[1-9]/[1-9]"; then
        echo -e "${GREEN}Redis Insight service is running!${NC}"
        break
    fi
    
    ATTEMPT=$((ATTEMPT+1))
    echo -e "${YELLOW}Waiting for Redis Insight to start... ($ATTEMPT/$MAX_ATTEMPTS)${NC}"
    sleep 5
    
    if [ $ATTEMPT -eq $MAX_ATTEMPTS ]; then
        echo -e "${RED}Timeout waiting for Redis Insight. Check logs with 'docker service logs redis_redis-insight'${NC}"
    fi
done

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
echo -e "${YELLOW}Deploying Chat History Stack...${NC}"
cd chat-history

# Build and tag the image explicitly
echo -e "${YELLOW}Building chat-history image...${NC}"
docker build -t mod/chat-history:latest .

# Deploy the stack
echo -e "${YELLOW}Deploying chat-history stack...${NC}"
export $(grep -v '^#' .env | xargs)
# docker stack deploy -c docker-compose.yml chat-history
envsubst < docker-compose.yml | docker stack deploy -c - chat-history
cd ..

# Deploy Orchestrator with Docker Swarm
echo -e "${YELLOW}Deploying Orchestrator Stack...${NC}"
cd orchestrator

# Build the orchestrator image
echo -e "${YELLOW}Building orchestrator image...${NC}"
docker build -t mod/orchestrator:latest .

# Deploy the stack
echo -e "${YELLOW}Deploying orchestrator stack...${NC}"
export $(grep -v '^#' .env | xargs)
# docker stack deploy -c docker-compose.yml orchestrator
envsubst < docker-compose.yml | docker stack deploy -c - orchestrator
cd ..

# Check deployment status of all services
echo -e "${YELLOW}Checking deployment status of all stacks...${NC}"
sleep 5
echo -e "${YELLOW}=== Services Status ===${NC}"
docker stack ls
echo -e "${YELLOW}=== Detailed Services Status ===${NC}"
docker service ls

echo -e "${GREEN}All services deployed successfully!${NC}"
echo -e "${GREEN}=== Access Information ===${NC}"
echo -e "Chat History API: http://localhost:8000"
echo -e "Redis: localhost:6379"
echo -e "Orchestrator: http://localhost:8082"
echo -e "Kafka UI: http://localhost:8080"

# Show current CLI .env content
echo -e "${YELLOW}Current CLI .env configuration:${NC}"
cat frontend/cli/src/cli/.env 2>/dev/null || echo "No .env file found for CLI"

echo
echo -e "${YELLOW}Make sure the above configuration is correct for your environment.${NC}"

echo -e "${GREEN}Deployment script finished.${NC}"
echo -e "${YELLOW}To stop all services run: ${NC}./undeploy.sh"
echo -e "${YELLOW}To view Docker Swarm services: ${NC}docker service ls"
echo -e "${YELLOW}To view logs for a service: ${NC}docker service logs <service_name>"

# Optionally show CLI help
if command -v uv &> /dev/null; then
    uv run frontend/cli/src/cli/client.py mod --help
fi