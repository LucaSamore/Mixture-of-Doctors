#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RAG_MODULE_DIR="$(dirname "$SCRIPT_DIR")"
ROOT_DIR="$(dirname "$RAG_MODULE_DIR")"

# Extract available domains from config.json
DOMAINS=$(grep -o '"[^"]*"' "$ROOT_DIR/config.json" | grep -v "rag_modules" | tr -d '"' | grep -v '[{}]')

echo "Stopping all RAG modules..."

for domain in $DOMAINS; do
    project_name="rag-$domain"
    echo "Stopping $project_name"
    docker-compose -p $project_name down
done

echo "All RAG modules stopped successfully!"