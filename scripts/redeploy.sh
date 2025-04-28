#!/bin/bash

set -e

# Check current directory and change to root if needed
CURRENT_DIR=$(basename "$PWD")
if [ "$CURRENT_DIR" = "scripts" ]; then
    cd ..
    echo "Changed directory to project root"
fi

# Include utility functions
source ./scripts/deploy_utils.sh

# Function to display help message
show_help() {
    echo -e "${GREEN}=== MoD Service Redeployment Script ===${NC}"
    echo -e "Usage: ./redeploy.sh [--service-name] [--all]"
    echo -e ""
    echo -e "Available options:"
    echo -e "  --all               Redeploy all services except databases and message brokers"
    echo -e "  --orchestrator      Redeploy only the orchestrator service"
    echo -e "  --synthesizer       Redeploy only the synthesizer service"
    echo -e "  --chat-history      Redeploy only the chat-history service"
    echo -e "  --rag-module        Redeploy only the RAG module services"
    echo -e "  --nginx             Redeploy only the nginx service"
    echo -e "  --help              Display this help message"
    echo -e ""
    echo -e "Example: ./redeploy.sh --orchestrator"
    echo -e "Note: Kafka, Redis, MongoDB, and Qdrant are excluded from redeployment to preserve data."
}

# Function to redeploy orchestrator service
redeploy_orchestrator() {
    echo -e "${YELLOW}=== Redeploying Orchestrator Service ===${NC}"
    
    # Remove existing orchestrator service if it exists
    if docker stack ls | grep -q "^orchestrator "; then
        echo -e "${YELLOW}Removing existing orchestrator service...${NC}"
        remove_stack "orchestrator"
    else
        echo -e "${YELLOW}Orchestrator service not found, deploying fresh...${NC}"
    fi
    
    # Wait for services to be completely removed
    sleep 5
    
    # Rebuild and redeploy orchestrator service
    echo -e "${YELLOW}Rebuilding and redeploying orchestrator service...${NC}"
    
    # Deploy orchestrator service
    deploy_service "orchestrator" "orchestrator" "mod/orchestrator:latest"
    
    echo -e "${GREEN}Orchestrator service redeployed successfully!${NC}"
}

# Function to redeploy synthesizer service
redeploy_synthesizer() {
    echo -e "${YELLOW}=== Redeploying Synthesizer Service ===${NC}"
    
    # Remove existing synthesizer service if it exists
    if docker stack ls | grep -q "^synthesizer "; then
        echo -e "${YELLOW}Removing existing synthesizer service...${NC}"
        remove_stack "synthesizer"
    else
        echo -e "${YELLOW}Synthesizer service not found, deploying fresh...${NC}"
    fi
    
    # Wait for services to be completely removed
    sleep 5
    
    # Rebuild and redeploy synthesizer service
    echo -e "${YELLOW}Rebuilding and redeploying synthesizer service...${NC}"
    
    # Deploy synthesizer service
    deploy_service "synthesizer" "synthesizer" "mod/synthesizer:latest"
    
    echo -e "${GREEN}Synthesizer service redeployed successfully!${NC}"
}

# Function to redeploy chat-history service
redeploy_chat_history() {
    echo -e "${YELLOW}=== Redeploying Chat-History Service ===${NC}"
    
    # Remove existing chat-history service if it exists
    if docker stack ls | grep -q "^chat-history "; then
        echo -e "${YELLOW}Removing existing chat-history service...${NC}"
        
        # Get service IDs for chat-history services (excluding MongoDB services)
        CHAT_HISTORY_SERVICE_IDS=$(docker service ls --filter "name=chat-history" --format "{{.ID}}" | grep -v "mongodb")
        
        # Remove only the chat-history service, keeping MongoDB
        for service_id in $CHAT_HISTORY_SERVICE_IDS; do
            echo -e "${YELLOW}Removing service: $service_id${NC}"
            docker service rm $service_id
        done
        
        # Wait for services to be completely removed
        echo -e "${YELLOW}Waiting for chat-history services to be removed...${NC}"
        while docker service ls --filter "name=chat-history" | grep -v "mongodb" | grep -q "chat-history"; do
            echo -n "."
            sleep 1
        done
        echo -e "${GREEN}Chat-history services removed${NC}"
    else
        echo -e "${YELLOW}Chat-history service not found, deploying fresh...${NC}"
    fi
    
    # Wait for services to be completely removed
    sleep 5
    
    # Rebuild and redeploy chat-history service
    echo -e "${YELLOW}Rebuilding and redeploying chat-history service...${NC}"
    
    # Deploy chat-history service
    deploy_service "chat-history" "chat-history" "mod/chat-history:latest"
    
    echo -e "${GREEN}Chat-history service redeployed successfully!${NC}"
}

# Function to redeploy nginx service
redeploy_nginx() {
    echo -e "${YELLOW}=== Redeploying Nginx Service ===${NC}"
    
    # Remove existing nginx service if it exists
    if docker stack ls | grep -q "^nginx "; then
        echo -e "${YELLOW}Removing existing nginx service...${NC}"
        remove_stack "nginx"
    else
        echo -e "${YELLOW}Nginx service not found, deploying fresh...${NC}"
    fi
    
    # Wait for services to be completely removed
    sleep 5
    
    # Redeploy nginx service
    echo -e "${YELLOW}Redeploying nginx service...${NC}"
    
    # Deploy nginx service (no image build needed)
    deploy_service "nginx" "infrastructure/nginx" ""
    
    echo -e "${GREEN}Nginx service redeployed successfully!${NC}"
}

# Function to redeploy RAG module services
redeploy_rag_module() {
    echo -e "${YELLOW}=== Redeploying RAG Services Only (Preserving Qdrant) ===${NC}"

    # Extract available domains from config.json
    DOMAINS=$(grep -o '"[^"]*"' "config.json" | grep -v "rag_modules" | tr -d '"' | grep -v '[{}]')

    # Remove only the RAG service containers but not the Qdrant databases
    for domain in $DOMAINS; do
        stack_name="rag-$domain"
        
        echo -e "${YELLOW}Redeploying RAG module for domain: $domain${NC}"
        
        # Check if the stack exists
        if docker stack ls | grep -q "^$stack_name "; then
            echo -e "${YELLOW}Removing existing RAG containers for domain: $domain${NC}"
            
            # Get the service IDs of the RAG module services (excluding Qdrant)
            RAG_SERVICE_IDS=$(docker service ls --filter "name=$stack_name" --filter "name=qdrant" --format "{{.ID}}" | grep -v "qdrant")
            
            # Remove only the RAG services, keeping Qdrant services
            for service_id in $RAG_SERVICE_IDS; do
                echo -e "${YELLOW}Removing service: $service_id${NC}"
                docker service rm $service_id
            done
            
            # Wait for services to be completely removed
            echo -e "${YELLOW}Waiting for RAG services to be completely removed...${NC}"
            while docker service ls --filter name=$stack_name --filter "name=qdrant" -q | grep -v "qdrant" | grep -q .; do
                echo -n "."
                sleep 1
            done
            echo -e "${GREEN}RAG services for $domain removed${NC}"
        else
            echo -e "${YELLOW}Stack $stack_name not found, deploying fresh...${NC}"
        fi
    done

    # Need to wait a bit before redeploying to ensure all services are properly removed
    echo -e "${YELLOW}Waiting a few seconds before redeploying...${NC}"
    sleep 5

    # Rebuild and redeploy RAG services
    echo -e "${YELLOW}Rebuilding and redeploying RAG services...${NC}"

    # Change to the rag-module directory
    cd rag-module

    # Build the RAG module image
    echo -e "${YELLOW}Building updated RAG module image...${NC}"
    docker build -t mixture-of-doctors/rag-module:latest .

    # Deploy RAG services for each domain, keeping existing Qdrant containers
    domain_index=0
    for domain in $DOMAINS; do
        echo -e "${YELLOW}Starting RAG module with domain: $domain${NC}"
        
        # Calculate ports for this domain (incrementing by 10 to avoid conflicts)
        QDRANT_REST_PORT=$((6333 + (domain_index * 10)))
        QDRANT_GRPC_PORT=$((6334 + (domain_index * 10)))
        
        # Define unique stack name for each domain
        stack_name="rag-$domain"
        
        # Export environment variables for docker-compose
        export RAG_DOMAIN=$domain
        export QDRANT_HOST="${stack_name}_qdrant"
        export QDRANT_PORT=6333
        export QDRANT_REST_PORT=$QDRANT_REST_PORT
        export QDRANT_GRPC_PORT=$QDRANT_GRPC_PORT

        # Load environment variables if .env exists
        if [ -f ".env" ]; then
            echo -e "${GREEN}Loading environment variables from .env file${NC}"
            set -a
            source .env
            set +a
        fi

        # Process docker-compose with environment variables
        envsubst < docker-compose.yml > docker-compose-processed.yml
        
        # Deploy using docker stack
        docker stack deploy -c docker-compose-processed.yml $stack_name
        
        echo -e "${GREEN}Redeployed $stack_name with Qdrant on port $QDRANT_REST_PORT${NC}"
        
        # Increment domain index for next iteration
        domain_index=$((domain_index + 1))
        
        # Clean up processed file
        rm docker-compose-processed.yml
    done

    # Return to original directory
    cd - > /dev/null

    echo -e "${GREEN}All RAG modules redeployed successfully!${NC}"
}

# Check if no arguments provided
if [ $# -eq 0 ]; then
    echo -e "${RED}Error: No arguments provided${NC}"
    show_help
    exit 1
fi

# Parse command-line arguments
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --orchestrator) redeploy_orchestrator; shift ;;
        --synthesizer) redeploy_synthesizer; shift ;;
        --chat-history) redeploy_chat_history; shift ;;
        --rag-module) redeploy_rag_module; shift ;;
        --nginx) redeploy_nginx; shift ;;
        --all)
            redeploy_orchestrator
            redeploy_synthesizer
            redeploy_chat_history 
            redeploy_rag_module
            redeploy_nginx
            shift 
            ;;
        --help)
            show_help
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown parameter: $1${NC}"
            show_help
            exit 1
            ;;
    esac
done

# Display service status
echo -e "${YELLOW}Checking deployment status...${NC}"
sleep 5
echo -e "${YELLOW}=== Services Status ===${NC}"
docker service ls

echo -e "${GREEN}Redeployment completed successfully!${NC}"
echo -e "${YELLOW}To check service logs: ${NC}docker service logs <service_name>"