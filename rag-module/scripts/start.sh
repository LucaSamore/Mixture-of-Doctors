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

# Change to the script directory where docker-compose.yml is located
cd "$SCRIPT_DIR"

# Loop through domains and start a RAG container for each
for domain in $DOMAINS; do
    echo "Starting RAG module with domain: $domain"
    # Define unique project name for each domain
    project_name="rag-$domain"
    
    # Use docker-compose up with a unique project name for each domain
    export RAG_DOMAIN=$domain
    docker-compose -p $project_name build --no-cache && docker-compose -p $project_name up -d
    
    echo "Started $project_name"
    # Short pause to avoid simultaneous startup issues
    sleep 1
done

echo "All RAG modules deployed!"