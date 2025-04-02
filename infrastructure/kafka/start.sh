#!/bin/bash

# Startup script for Kafka with KRaft and UI

# Colors for messages
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

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

kafka-topics.sh --bootstrap-server kafka:9092 --create --if-not-exists \
  --topic diabetes \
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

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}Docker is not running. Please start Docker and try again.${NC}"
    exit 1
fi

# Clean up existing containers to avoid cached scripts
echo -e "${YELLOW}Removing any existing containers to ensure clean state...${NC}"
docker-compose down -v

# Remove any existing kafka-init container to ensure script is reloaded
EXISTING_CONTAINER=$(docker ps -a --filter name=kafka-init --format "{{.ID}}")
if [ ! -z "$EXISTING_CONTAINER" ]; then
    echo -e "${YELLOW}Removing existing kafka-init container...${NC}"
    docker rm $EXISTING_CONTAINER
fi

# Start containers with force-recreate to ensure fresh instances
echo -e "${YELLOW}Starting Kafka and UI containers...${NC}"
docker-compose build --no-cache
docker-compose up -d --force-recreate

# Wait for Kafka to start
echo -e "${YELLOW}Waiting for Kafka to start...${NC}"
sleep 10

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

# Wait for UI to start
echo -e "${YELLOW}Waiting for Kafka UI to start...${NC}"
ATTEMPT=0
while [ $ATTEMPT -lt $MAX_ATTEMPTS ]; do
    if curl -s http://localhost:8080/actuator/health > /dev/null 2>&1; then
        echo -e "${GREEN}Kafka UI is ready!${NC}"
        
        # Show useful information
        echo -e "${GREEN}=== Connection Information ===${NC}"
        echo -e "Kafka Broker: localhost:9094"
        echo -e "Docker internal: kafka:9092"
        echo -e "${GREEN}=== UI Access ===${NC}"
        echo -e "Kafka UI: http://localhost:8080"
        echo -e "${YELLOW}To terminate the environment: ${NC}docker-compose down"
        echo -e "${YELLOW}To view logs: ${NC}docker-compose logs -f"
        exit 0
    fi
    
    ATTEMPT=$((ATTEMPT+1))
    echo -e "${YELLOW}Waiting for Kafka UI... ($ATTEMPT/$MAX_ATTEMPTS)${NC}"
    sleep 5
done

echo -e "${RED}Timeout during Kafka UI startup. Check logs with 'docker-compose logs kafka-ui'${NC}"
exit 1