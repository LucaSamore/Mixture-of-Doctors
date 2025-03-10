import os
import json
from typing import List

CONFIG_PATH = "/app/config.json"


def load_domains_from_config(config_path: str) -> List[str]:
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)
        return config.get("rag_modules", [])


def initialize_rag() -> str:
    # Get domain from environment variable
    domain = os.environ.get("RAG_DOMAIN")
    if not domain:
        raise ValueError("RAG_DOMAIN environment variable must be set")

    # Load configuration from file
    valid_domains = load_domains_from_config(CONFIG_PATH)

    # Validate that the domain is supported
    if domain not in valid_domains:
        raise ValueError(f"Domain '{domain}' not found in configuration file")

    # Print configuration at startup to help with debugging
    print(f"Initialized RAG module for domain: {domain}", flush=True)

    return domain


def main():
    """Initialize and run the RAG module"""
    try:
        # Initialize the RAG module
        domain = initialize_rag()
        print(f"RAG module initialized successfully for domain: {domain}", flush=True)

        print("Service running. Press Ctrl+C to exit.", flush=True)
        try:
            while True:
                pass
        except KeyboardInterrupt:
            print("\nService stopped.", flush=True)

        # Normally, the RAG module would run here

    except Exception as e:
        print(f"Error initializing RAG module: {e}", flush=True)
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
