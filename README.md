TODO IMMAGINI
# Mixture of Doctors

An agentic-RAG system for self-management of chronic diseases

## Introduction

Mixture of Doctors (MoD) is an advanced agentic-RAG system designed to support patients in managing chronic conditions through accurate and empathetic guidance. The system leverages specialized "doctor" agents, each focused on a specific condition (diabetes, multiple sclerosis, and hypertension), to provide reliable information while addressing key challenges in healthcare AI:

- **Hallucination mitigation** through Retrieval-Augmented Generation
- **Privacy protection** with locally processed open-source LLMs
- **Cross-condition expertise** for comprehensive care

## Architecture

MoD uses an Orchestrator-workers architecture where:
- An **Orchestrator** analyzes queries and routes them to appropriate specialists
- **Doctor modules** retrieve relevant information and generate responses
- A **Synthesizer** combines responses for cross-domain questions

Communication uses Kafka for messaging, Redis for streaming, and Qdrant for vector storage.

## Deployment

MoD uses Docker Swarm for orchestration and service management, providing service isolation, scalability, and simplified dependency management.

### System Deployment

1. Ensure Docker and Docker Swarm are installed and properly configured
2. Clone the repository:
   ```bash
   git clone https://github.com/LucaSamore/Mixture-of-Doctors
   ```
3. Run the automated deployment script:
	```bash
   ./scripts/deploy.sh
   ```
Optionally, preload the vector store in RAG modules with domain-specific corpora:
```bash
	./scripts/deploy.sh --ingest
```

### Redeployment
Individual services can be selectively redeployed:
```bash
	./scripts/redeploy.sh --<service-name>
```
Available service options:
- `--orchestrator`
- `--synthesizer`
- `--chat-history`
- `--rag-module`
- `--nginx`
- `--cli`
- `--all` (redeploys all application services without affecting databases and message brokers)

### Undeployment
```bash
For controlled shutdown and environment cleanup:
	./scripts/undeploy.sh
```
Available flags:
- `--volumes`: Removes all persistent data volumes
- `--points`: Clears vector embeddings without altering configuration files

## User guide
After successful deployment, an interactive command-line interface (CLI REPL) is presented:

### Basic Commands

| Command | Description |
|---------|-------------|
| `mod new <username>` | Create new session |
| `mod restore <username>` | Load existing chat history |
| `mod chat <username>` | Automatically create or restore session |
| `mod ask "<question>"` | Ask a health question |
| `mod ask "<question>" --oneshot` | Ask without saving to history |
| `mod quit` | End session |
| `help` | Show all commands |
| `quit` or `exit` | Exit the REPL interface |

### Example Session
1. Start a new session:
```bash
	mod new john
```

2. Ask health-related questions:
```bash
	mod ask "What lifestyle changes can help manage my diabetes?"
```

3. Ask cross-condition questions:
```bash
	mod ask "How does hypertension affect multiple sclerosis symptoms?"
```

4. End your session:
```bash
	mod quit
```

5. Later, restore your previous session:
```bash
	mod restore john
```

## Technical Details

The system is composed of several key components:

- **Orchestrator**: Central coordination hub that manages request distribution
- **RAG Modules**: Specialized "doctors" that retrieve relevant information and generate responses
- **Synthesizer**: Aggregates responses from multiple RAG modules for cross-domain queries
- **Chat History**: Maintains conversation context and history

Communication between components uses:
- Apache Kafka for asynchronous messaging
- Redis Streams for real-time response streaming
- Qdrant Vector Database for knowledge storage
- Groq LLM API for inference
- NGINX as a reverse proxy

## Limitations and Future Work

While the initial interface is CLI-based, the system is built around RESTful APIs, making it extensible to graphical interfaces (web or mobile) in future development. This modular design ensures flexibility, scalability, and ease of integration with other platforms.

## Contributors

- Luca Samorè (luca.samore@studio.unibo.it)
- Lucia Castellucci (lucia.castellucci2@studio.unibo.it)
- Roberto Mitugno (roberto.mitugno@studio.unibo.it)

## License