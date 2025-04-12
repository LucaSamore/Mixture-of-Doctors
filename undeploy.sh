#!/bin/bash

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Parse command line arguments
REMOVE_VOLUMES=false
if [ "$1" == "--volumes" ] || [ "$1" == "-v" ]; then
    REMOVE_VOLUMES=true
    echo -e "${YELLOW}WARNING: Will remove all volumes (data will be lost)${NC}"
fi

echo -e "${YELLOW}=== Undeploying all Docker Swarm stacks ===${NC}"

# Function to remove a stack and wait for it to be fully removed
remove_stack() {
    local stack_name=$1
    
    if docker stack ls | grep -q "^$stack_name "; then
        echo -e "${YELLOW}Removing $stack_name stack...${NC}"
        docker stack rm $stack_name
        
        # Wait for all services to be removed
        echo -e "${YELLOW}Waiting for $stack_name services to be completely removed...${NC}"
        while docker service ls --filter name=$stack_name -q | grep -q .; do
            echo -n "."
            sleep 2
        done
        echo -e "\n${GREEN}All $stack_name services removed${NC}"
    else
        echo -e "${YELLOW}Stack $stack_name not found, skipping...${NC}"
    fi
}

# Remove all stacks in reverse order of deployment
remove_stack "orchestrator"
remove_stack "chat-history" 
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