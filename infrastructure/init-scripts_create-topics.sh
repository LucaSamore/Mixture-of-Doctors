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

# Create topic: rag-module
kafka-topics.sh --bootstrap-server kafka:9092 --create --if-not-exists \
  --topic rag-module \
  --partitions 3 \
  --replication-factor 1

# List created topics
echo "Topics created successfully! Current topics:"
kafka-topics.sh --bootstrap-server kafka:9092 --list

echo "Topic initialization complete!"