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

# Deploy kafka first
echo -e "${YELLOW}=== Starting Kafka with KRaft and UI environment ===${NC}"

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

# Create topic: orchestrator
kafka-topics.sh --bootstrap-server kafka:9092 --create --if-not-exists \
  --topic orchestrator \
  --partitions 3 \
  --replication-factor 1

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

echo -e "${YELLOW}Deploying Kafka...${NC}"
cd infrastructure/kafka
docker compose up -d

# Verify that Kafka service is available
MAX_ATTEMPTS=12
ATTEMPT=0
while [ $ATTEMPT -lt $MAX_ATTEMPTS ]; do
    if docker-compose exec kafka kafka-topics.sh --bootstrap-server kafka:9092 --list > /dev/null 2>&1; then
        echo -e "${GREEN}Kafka is ready!${NC}"
        break
    fi
    
    ATTEMPT=$((ATTEMPT+1))
    echo -e "${YELLOW}Waiting for Kafka... ($ATTEMPT/$MAX_ATTEMPTS)${NC}"
    sleep 5
    
    if [ $ATTEMPT -eq $MAX_ATTEMPTS ]; then
        echo -e "${RED}Timeout during Kafka startup. Check logs with 'docker-compose logs kafka'${NC}"
        exit 1
    fi
done

echo -e "${YELLOW}Waiting for Kafka UI to start...${NC}"
ATTEMPT=0
while [ $ATTEMPT -lt $MAX_ATTEMPTS ]; do
    if curl -s http://localhost:8080/actuator/health > /dev/null 2>&1; then
        echo -e "${GREEN}Kafka UI is ready!${NC}"
        break
    fi
    
    ATTEMPT=$((ATTEMPT+1))
    echo -e "${YELLOW}Waiting for Kafka UI... ($ATTEMPT/$MAX_ATTEMPTS)${NC}"
    sleep 5

    if [ $ATTEMPT -eq $MAX_ATTEMPTS ]; then
        echo -e "${RED}Timeout during Kafka UI startup. Check logs with 'docker-compose logs kafka-ui'${NC}"
        break
    fi
done
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