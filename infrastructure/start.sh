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

kafka-topics.sh --bootstrap-server kafka:9092 --create --if-not-exists \
  --topic multiple-sclerosis \
  --partitions 3 \
  --replication-factor 1

kafka-topics.sh --bootstrap-server kafka:9092 --create --if-not-exists \
  --topic hypertension \
  --partitions 3 \
  --replication-factor 1

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

# Start containers
echo -e "${YELLOW}Starting Kafka and UI containers...${NC}"
docker-compose up -d

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
        echo -e "${GREEN}=== Pre-configured Topics ===${NC}"
        echo -e "1. orchestrator"
        echo -e "2. rag-module"
        echo -e ""
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