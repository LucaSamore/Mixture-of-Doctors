#!/bin/bash

# This script launches RAG services scaled with different domains

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RAG_MODULE_DIR="$(dirname "$SCRIPT_DIR")"
ROOT_DIR="$(dirname "$RAG_MODULE_DIR")"

# Check if config.json exists in the root directory
if [ ! -f "$ROOT_DIR/config.json" ]; then
    echo "Error: config.json not found in the root directory!"
    exit 1
fi

# Extract available domains from config.json
DOMAINS=$(grep -o '"[^"]*"' "$ROOT_DIR/config.json" | grep -v "rag_modules" | tr -d '"' | grep -v '[{}]')

echo "Found domains: $DOMAINS"

# Change to the rag-module directory where docker-compose.yml is located
cd "$RAG_MODULE_DIR"

# Base port for REST API (will be incremented for each domain)
BASE_REST_PORT=6333
# Base port for gRPC API (will be incremented for each domain)
BASE_GRPC_PORT=6334

# Loop through domains and start a RAG container for each with its own Qdrant
domain_index=0
for domain in $DOMAINS; do
    echo "Starting RAG module with domain: $domain"
    
    # Calculate ports for this domain (incrementing by 10 to avoid conflicts)
    QDRANT_REST_PORT=$((BASE_REST_PORT + (domain_index * 10)))
    QDRANT_GRPC_PORT=$((BASE_GRPC_PORT + (domain_index * 10)))
    
    # Define unique project name for each domain
    project_name="rag-$domain"
    
    # Export environment variables for docker-compose
    export RAG_DOMAIN=$domain
    export QDRANT_REST_PORT=$QDRANT_REST_PORT
    export QDRANT_GRPC_PORT=$QDRANT_GRPC_PORT
    
    # Build and start both rag and qdrant services for this domain
    docker-compose -p $project_name build rag --no-cache
    docker-compose -p $project_name up -d
    
    echo "Started $project_name with Qdrant on port $QDRANT_REST_PORT"
    echo "Qdrant dashboard for $domain available at: http://localhost:$QDRANT_REST_PORT/dashboard"
    
    # Increment domain index for next iteration
    domain_index=$((domain_index + 1))
    
    # Short pause to avoid simultaneous startup issues
    sleep 1
done

echo "All RAG modules deployed!"
echo "Check above for the specific Qdrant dashboard URLs for each domain"

# Install dependencies for ingestion script
echo "Installing required dependencies for ingestion..."
cd "$RAG_MODULE_DIR/ingestion/"
pip install -r requirements.txt

echo "Starting data ingestion for each domain..."

domain_index=0
for domain in $DOMAINS; do
    echo "Deleting all points in the Qdrant collection for domain: $domain"
    QDRANT_REST_PORT=$((BASE_REST_PORT + (domain_index * 10)))
    curl -X POST "http://localhost:$QDRANT_REST_PORT/collections/${domain}_docs/points/delete" \
        -H "Content-Type: application/json" \
        -d '{"filter": {}}'

    if [ $? -ne 0 ]; then
        echo "Error: Failed to delete points for domain $domain"
        exit 1
    fi

    echo "All points deleted for domain: $domain"

    # Increment domain index for next iteration
    domain_index=$((domain_index + 1))

done

domain_index=0
for domain in $DOMAINS; do
    echo "Deleting all points in the Qdrant collection for domain: $domain"
    QDRANT_REST_PORT=$((BASE_REST_PORT + (domain_index * 10)))
    curl -X POST "http://localhost:$QDRANT_REST_PORT/collections/${domain}_docs/points/delete" \
        -H "Content-Type: application/json" \
        -d '{"filter": {}}'

    if [ $? -ne 0 ]; then
        echo "Error: Failed to delete points for domain $domain"
        exit 1
    fi

    echo "All points deleted for domain: $domain"

    # Increment domain index for next iteration
    domain_index=$((domain_index + 1))

done

domain_index=0
for domain in $DOMAINS; do
    echo "Running ingestion for domain: $domain"
    python ingest_pubmed.py --domain $domain --query "$domain disease" --count 10
done

echo "Ingestion complete for all domains!"