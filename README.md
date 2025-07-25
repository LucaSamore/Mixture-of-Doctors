# Mixture of Doctors

An agentic-RAG system for self-management of chronic diseases.

## 📖 Overview

Supporting patients in the self-management of chronic diseases requires continuous, personalized guidance, a task for which LLM-powered chatbots show immense promise. However, their deployment is contingent on overcoming a dual challenge: the inherent risk of LLM "hallucinations" and the architectural complexity of building a system that can manage multiple medical domains securely.

**Mixture of Doctors (MoD)** is an agentic-RAG system designed to address these challenges in tandem. Its core mission is to provide trustworthy, accurate, and empathetic guidance to patients with chronic conditions.

### Key Features
- **🩺 Specialized Expertise**: The system employs multiple "Doctor" components, each an expert on a specific chronic disease (e.g., Diabetes, Multiple Sclerosis, Hypertension).
- **🛡️ Hallucination Mitigation**: Responses are grounded in curated medical knowledge bases using a Retrieval-Augmented Generation (RAG) pipeline, ensuring factual accuracy.
- **🧠 Agentic Orchestration**: A central Orchestrator dynamically analyzes user queries, decomposes complex cross-domain questions, and routes them to the appropriate specialists.
- **🔐 Data Privacy**: The system is built with open-source technologies and designed for local deployment, ensuring sensitive user data remains secure.

## 🏗️ System Architecture

MoD is built upon a decoupled **Orchestrator-worker architecture** that leverages asynchronous messaging for resilience and scalability.

### Core Components
- **Orchestrator**: The central coordination hub. It receives user queries, uses an LLM to determine query complexity (`easy`, `medium`, `hard`), and delegates tasks to the appropriate workers.
- **Doctor (RAG Module)**: A specialized worker focused on a single chronic disease. It uses a RAG pipeline to generate evidence-based answers from a dedicated vector database.
- **Synthesizer**: An aggregation component that receives responses from multiple Doctors for `hard` (cross-domain) queries and synthesizes them into a single, cohesive answer.
- **Chat History**: A dedicated service for persisting and retrieving user conversation logs, providing long-term memory for the system.

### Interaction Flow
- **Easy Queries**: Handled synchronously by the Orchestrator for immediate, low-latency responses.
- **Medium & Hard Queries**: Processed asynchronously via a publish-subscribe pattern using a message broker to ensure resilience and fault tolerance.

## 🛠️ Technologies Used

The system is built using a modern, scalable stack of open-source technologies:

| Category | Technology | Purpose |
| :--- | :--- | :--- |
| **Orchestration** | **Docker Swarm** | Container orchestration, scaling, and service management. |
| **Gateway** | **NGINX** | Reverse proxy, SSL/TLS termination, and request routing. |
| **Messaging** | **Apache Kafka** | Asynchronous, fault-tolerant communication between services. |
| **Streaming/Cache** | **Redis Streams** | Real-time, token-by-token streaming of responses to the client. |
| **Knowledge Base** | **Qdrant** | High-performance vector database for RAG retrieval. |
| **Persistence** | **MongoDB** | Document database for storing user chat histories. |
| **LLM Inference** | **Groq API** | High-speed inference for LLMs (e.g., Llama 3.3 70B). |
| **Backend** | **Python** | Core application logic, with **FastAPI** for APIs and **Typer** for the CLI. |

## 🚀 Deployment and Setup

The system is designed to be deployed as a set of containerized services using Docker Swarm.

### Prerequisites
- **Docker** & **Docker Swarm** must be installed and properly configured on your machine.

### 1. Environment Configuration
Before deploying, you must configure the environment variables.

1.  Navigate to the `scripts` directory.
2.  Copy the example environment file:
    
	```bash
    cp setup_envs.example.sh setup_envs.sh
    ```
3.  Open `setup_envs.sh` with a text editor and fill in the required values (e.g., API keys, secrets).
4.  Launch `setup_envs.sh` script:

    ```bash
    ./scripts/setup_envs.sh
    ```

### 2. System Deployment
From the project's root directory, run the automated deployment script:
```bash
./scripts/deploy.sh
```
This will build and launch all services. The CLI will appear in your terminal, ready for interaction.

**Optional: Data Ingestion**
To preload the RAG modules' knowledge bases with domain-specific documents, use the `--ingest` flag:
```bash
./scripts/deploy.sh --ingest
```

### 3. Redeployment
To update a single service without restarting the entire stack:
```bash
./scripts/redeploy.sh --<service-name>
```
Available services include `--orchestrator`, `--synthesizer`, `--rag-module`, `--cli`, `--nginx`, `--chat-history`, and `--all`.

### 4. Undeployment
To stop and remove all services and containers:
```bash
./scripts/undeploy.sh
```
**Flags:**
- `--volumes`: Removes all persistent data (databases, message queues).
- `--points`: Clears only the vector embeddings in Qdrant.

## 💻 User Guide

After deployment, you can interact with the system via the interactive CLI (REPL).

### Command Reference

| Command | Description |
|:---|:---|
| `mod new <username>` | Creates a new chat session for a user. |
| `mod restore <username>` | Loads a user's existing chat history. |
| `mod chat <username>` | Automatically creates a new session or restores an existing one. |
| `mod ask "<question>"` | Asks a question to the system. The conversation is saved. |
| `mod ask "<question>" --oneshot` | Asks a question without saving it to the chat history. |
| `mod quit` | Ends the current user session and cleans up auth files. |
| `help` | Shows all available commands. |
| `quit` or `exit` | Exits the REPL interface. |

### Example Usage

1.  **Start a new session for a user named "luca"**:
    ```bash
    mod new luca
    ```

2.  **Ask a question about a single condition (Medium Query)**:
    ```bash
    mod ask "What are the early signs of diabetes?"
    ```

3.  **Ask a cross-domain question (Hard Query)**:
    ```bash
    mod ask "How does hypertension impact the management of multiple sclerosis?"
    ```

4.  **End the session**:
    ```bash
    mod quit
    ```

5.  **Return later and restore the conversation**:
    ```bash
    mod restore luca
    ```

## 🎯 Limitations and Future Work

### Current Limitations
- **Finite Context Window**: Long conversations are limited by the LLM's context size.
- **Standard RAG Pipeline**: The system uses a single-pass RAG, which may be insufficient for highly complex reasoning.
- **Minimal Security**: The prototype lacks a formal authentication/authorization layer and robust prompt injection defenses.

### Future Enhancements
- **Advanced UI**: Develop a graphical user interface (web or mobile).
- **Rigorous Evaluation**: Implement quantitative metrics to evaluate RAG performance.
- **GraphRAG Migration**: Transition to a graph-based RAG for more sophisticated, interconnected reasoning.
- **Evolve to a Multi-Agent System**: Enhance Doctor modules into autonomous agents with richer internal reasoning loops.
- **Automated Ingestion Pipeline**: Create a pipeline to keep knowledge bases automatically updated.
- **Comprehensive Security**: Add a dedicated authentication service and robust security protocols.

## 👥 Authors

- **Luca Samorè** - [luca.samore@studio.unibo.it](mailto:luca.samore@studio.unibo.it)
- **Lucia Castellucci** - [lucia.castellucci2@studio.unibo.it](mailto:lucia.castellucci2@studio.unibo.it)
- **Roberto Mitugno** - [roberto.mitugno@studio.unibo.it](mailto:roberto.mitugno@studio.unibo.it)