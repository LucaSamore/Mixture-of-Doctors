#!/bin/bash

# Colors for terminal output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}Creating .env files for Mixture-of-Doctors project...${NC}"

# 1. Create infrastructure/redis/.env
cat > ../infrastructure/redis/.env << EOF
REDIS_VERSION=
REDIS_USERNAME=
REDIS_PASSWORD=
REDIS_PORT=
REDIS_NAME=
REDIS_HOST=

REDIS_INSIGHT_VERSION=
REDIS_INSIGHT_PORT=
EOF
echo -e "${GREEN}Created${NC} infrastructure/redis/.env"

# 2. Create infrastructure/kafka/.env
cat > ../infrastructure/kafka/.env << EOF
KAFKA_VERSION=
KAFKA_PORT=
KAFKA_EXTERNAL_PORT=
KAFKA_KRAFT_CLUSTER_ID=
KAFKA_UI_PORT=
EOF
echo -e "${GREEN}Created${NC} infrastructure/kafka/.env"

# 3. Create orchestrator/.env
cat > ../orchestrator/.env << EOF
ORCHESTRATOR_PORT=
CLUSTER_HOST=
CLUSTER_PORT=
KAFKA_BROKER=
REDIS_HOST=
REDIS_PASSWORD=
REDIS_PORT=
CHAT_HISTORY_URL=
GROQ_API_KEY=
EOF
echo -e "${GREEN}Created${NC} orchestrator/.env"

# 4. Create frontend/cli/src/cli/.env
cat > ../frontend/cli/src/cli/.env << EOF
REDIS_HOST=
REDIS_PORT=
REDIS_PASSWORD=
USER_ID=
ORCHESTRATOR_URL=
REQUEST_TIMEOUT=
CHAT_HISTORY_API_URL=
EOF
echo -e "${GREEN}Created${NC} frontend/cli/src/cli/.env"

# 5. Create chat-history/.env
cat > ../chat-history/.env << EOF
CHAT_HISTORY_HOST_PORT=
CHAT_HISTORY_CONTAINER_PORT=

MONGODB_URL=
MONGODB_DB=

MONGO_UI_PORT=
MONGO_UI_HOST=

MONGO_PRIMARY_HOST=
MONGO1_PORT=
MONGO2_PORT=
MONGO3_PORT=
EOF
echo -e "${GREEN}Created${NC} chat-history/.env"

# 6. Create rag-module/.env
cat > ../rag-module/.env << EOF
RAG_SERVICE_PORT=
RAG_DEFAULT_DOMAIN=
QDRANT_HOST=
QDRANT_PORT=
QDRANT_REST_PORT=
QDRANT_GRPC_PORT=
QDRANT_ALLOW_ANONYMOUS=
KAFKA_BROKER=
KAFKA_PRODUCER_TOPIC=
GROQ_API_KEY=
EOF
echo -e "${GREEN}Created${NC} rag-module/.env"

# 6. Create synthesizer/.env
cat > ../synthesizer/.env << EOF
REDIS_PORT=
REDIS_HOST=
REDIS_PASSWORD=
KAFKA_BROKER=
GROQ_API_KEY=
EOF
echo -e "${GREEN}Created${NC} synthesizer/.env"

# Create logs directory for orchestrator
mkdir -p ../orchestrator/logs

echo -e "${YELLOW}All .env files have been created successfully!${NC}"