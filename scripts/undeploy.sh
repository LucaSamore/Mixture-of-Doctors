#!/bin/bash

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check current directory and change to root if needed
CURRENT_DIR=$(basename "$PWD")
if [ "$CURRENT_DIR" = "scripts" ]; then
    cd ..
    echo -e "${GREEN}Changed directory to project root${NC}"
fi

# Import utility functions
source scripts/deploy_utils.sh

# Parse command line arguments
REMOVE_VOLUMES=false
if [ "$1" == "--volumes" ] || [ "$1" == "-v" ] || [ "$2" == "--volumes" ] || [ "$2" == "-v" ] ; then
    REMOVE_VOLUMES=true
    echo -e "${YELLOW}WARNING: Will remove all volumes (data will be lost)${NC}"
fi

REMOVE_POINTS=false
if [ "$1" == "--points" ] || [ "$1" == "-p" ] || [ "$2" == "--points" ] || [ "$2" == "-p" ]; then
    REMOVE_POINTS=true
    echo -e "${YELLOW}WARNING: Will remove all points on vector stores (data will be lost)${NC}"
fi

# Remove CLI container
echo -e "${YELLOW}=== Removing CLI container ===${NC}"
if docker ps -a --format '{{.Names}}' | grep -q "^mod-cli$"; then
    docker stop mod-cli >/dev/null 2>&1
    docker rm mod-cli >/dev/null 2>&1
    echo -e "${GREEN}CLI container removed successfully${NC}"
else
    echo -e "${YELLOW}CLI container not found, skipping removal${NC}"
fi


echo -e "${YELLOW}=== Undeploying all Docker Swarm stacks ===${NC}"

# Remove all stacks in reverse order of deployment
remove_stack "nginx"
remove_stack "orchestrator"
remove_stack "synthesizer"
remove_stack "chat-history" 
remove_stack "redis"
remove_stack "kafka"

# If --points flag is used, delete points
if [ "$REMOVE_POINTS" = true ]; then
    echo -e "${YELLOW}\nDelete all points in each rag-module's vector store...${NC}"

    # Delete points from Qdrant collections if they exist
    # Extract available domains from config.json
    ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    DOMAINS=$(grep -o '"[^"]*"' "$ROOT_DIR/config.json" | grep -v "rag_modules" | tr -d '"' | grep -v '[{}]')
    BASE_REST_PORT=6333

    domain_index=0
    for domain in $DOMAINS; do
        echo -e "${YELLOW}\nProcessing domain: $domain${NC}"
        QDRANT_REST_PORT=$((BASE_REST_PORT + (domain_index * 10)))
        
        # First check if the collection exists
        COLLECTION_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:$QDRANT_REST_PORT/collections/${domain}_docs")

        if [ "$COLLECTION_STATUS" = "200" ]; then
            echo -e "${YELLOW}Deleting all points in the Qdrant collection for domain: $domain${NC}"
            DELETE_RESPONSE=$(curl -s -X POST "http://localhost:$QDRANT_REST_PORT/collections/${domain}_docs/points/delete" \
                -H "Content-Type: application/json" \
                -d '{"filter": {}}')
                
            if echo "$DELETE_RESPONSE" | grep -q "error"; then
                echo -e "${RED}Warning: Issue deleting points for domain $domain: $DELETE_RESPONSE${NC}"
                # Continue anyway, don't exit
            else
                echo -e "${GREEN}All points deleted for domain: $domain${NC}"
            fi
        else
            echo -e "${YELLOW}Collection ${domain}_docs does not exist, no need to delete points${NC}"
        fi

        # Increment domain index for the next domain
        domain_index=$((domain_index + 1))
    done
fi

# Remove all RAG module stacks
echo -e "${YELLOW}\nRemoving all RAG module stacks...${NC}"
# Extract available domains from config.json to find all RAG module stacks
DOMAINS=$(grep -o '"[^"]*"' "config.json" | grep -v "rag_modules" | tr -d '"' | grep -v '[{}]')
for domain in $DOMAINS; do
    remove_stack "rag-$domain"
done

# Check if username.txt file exists in frontend/cli/src/cli and delete it
USERNAME_FILE="frontend/cli/src/cli/username.txt"
if [ -f "$USERNAME_FILE" ]; then
    echo -e "${YELLOW}\nRemoving username.txt file from CLI...${NC}"
    rm -f "$USERNAME_FILE"
    echo -e "${GREEN}username.txt removed successfully${NC}"
fi

# If --volumes flag is used, prune volumes
if [ "$REMOVE_VOLUMES" = true ]; then
    echo -e "${YELLOW}\nPruning all volumes...${NC}"
            
    # Stop all containers first to release any volume locks
    echo -e "${YELLOW}Stopping all running containers...${NC}"
    if docker ps -q | grep -q .; then
        docker stop $(docker ps -q)
    fi
    
    # Get all volume names
    VOLUMES=$(docker volume ls -q)
    if [ -n "$VOLUMES" ]; then
        for vol in $VOLUMES; do
            echo -e "${YELLOW}Removing volume: $vol${NC}"
            docker volume rm $vol --force 2>/dev/null || true
            sleep 1
        done
    fi
    
    # Final pruning to catch anything left
    docker volume prune -f
    
    echo -e "${GREEN}Volumes cleanup completed${NC}"
fi

# Check if swarm network still exists and remove if not in use
echo -e "${YELLOW}\nChecking if mod-network (swarm scope) can be removed... (it could take a few seconds)${NC}"
sleep 20  # Give Docker time to update network usage status

if docker network ls --filter name=mod-network --filter scope=swarm -q | grep -q .; then
    # Check if any containers are still using it
    USED_BY=$(docker network inspect mod-network -f '{{len .Containers}}' 2>/dev/null || echo "0")
    
    if [ "$USED_BY" -eq "0" ]; then
        echo -e "${YELLOW}Removing mod-network swarm network...${NC}"
        docker network rm mod-network
        echo -e "${GREEN}Network mod-network removed${NC}"
    else
        echo -e "${YELLOW}Network mod-network is still in use by $USED_BY containers, skipping removal.${NC}"
    fi
else
    echo -e "${YELLOW}Network mod-network not found, skipping removal.${NC}"
fi

echo -e "${GREEN}=== All stacks undeployed successfully! ===${NC}"

if [ "$REMOVE_VOLUMES" != true ]; then
    echo -e "${YELLOW}Note: Volumes were preserved. Use './undeploy.sh --volumes' to remove all data.${NC}"
fi

if [ "$REMOVE_POINTS" != true ]; then
    echo -e "${YELLOW}Note: Vectore store's points were preserved. Use './undeploy.sh --points' to remove all data.${NC}"
fi