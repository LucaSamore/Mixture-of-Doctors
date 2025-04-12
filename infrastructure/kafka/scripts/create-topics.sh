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
