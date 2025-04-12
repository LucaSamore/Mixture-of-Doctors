#!/bin/bash

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Import utility functions
source scripts/deploy_utils.sh

# Parse command line arguments
REMOVE_VOLUMES=false
if [ "$1" == "--volumes" ] || [ "$1" == "-v" ]; then
    REMOVE_VOLUMES=true
    echo -e "${YELLOW}WARNING: Will remove all volumes (data will be lost)${NC}"
fi

echo -e "${YELLOW}=== Undeploying all Docker Swarm stacks ===${NC}"

# Remove all stacks in reverse order of deployment
remove_stack "orchestrator"
remove_stack "chat-history" 

# Remove all RAG module stacks
echo -e "${YELLOW}Removing all RAG module stacks...${NC}"
# Extract available domains from config.json to find all RAG module stacks
DOMAINS=$(grep -o '"[^"]*"' "config.json" | grep -v "rag_modules" | tr -d '"' | grep -v '[{}]')
for domain in $DOMAINS; do
    remove_stack "rag-$domain"
done

remove_stack "redis"
remove_stack "kafka"

# If --volumes flag is used, prune volumes
if [ "$REMOVE_VOLUMES" = true ]; then
    echo -e "${YELLOW}Pruning all unused volumes...${NC}"
    docker volume prune -f
    echo -e "${GREEN}Volumes pruned${NC}"
fi

# Check if swarm network still exists and remove if not in use
echo -e "${YELLOW}Checking if mod-network (swarm scope) can be removed...${NC}"
sleep 10  # Give Docker time to update network usage status

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