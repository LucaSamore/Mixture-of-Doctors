import argparse
import requests
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.http import models
import uuid
import json
import re

# Optimized for all-MiniLM-L6-v2
CHUNK_SIZE = 384  # Optimal for this model
OVERLAP = 1  # Number of sentences to overlap


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Ingest PubMed articles into Qdrant vector store"
    )
    parser.add_argument(
        "--domain",
        type=str,
        required=True,
        help="Domain name (e.g., alzheimer, parkinson, epilepsy)",
    )
    parser.add_argument("--query", type=str, required=True, help="PubMed search query")
    parser.add_argument(
        "--count", type=int, default=10, help="Number of articles to retrieve"
    )
    parser.add_argument("--host", type=str, default="localhost", help="Qdrant host")
    parser.add_argument(
        "--port",
        type=int,
        help="Qdrant REST port (calculated from domain if not provided)",
    )
    parser.add_argument(
        "--chunk_size",
        type=int,
        default=CHUNK_SIZE,
        help=f"Target size of text chunks in tokens (default: {CHUNK_SIZE})",
    )
    parser.add_argument(
        "--overlap",
        type=int,
        default=OVERLAP,
        help=f"Number of sentences to overlap between chunks (default: {OVERLAP})",
    )
    return parser.parse_args()


def get_domain_port(domain, base_port=6333):
    try:
        with open("../../config.json", "r") as f:
            config = json.load(f)
            domains = config.get("rag_modules", [])
            if domain in domains:
                domain_index = domains.index(domain)
                return base_port + (domain_index * 10)
    except Exception as e:
        print(f"Error loading config: {e}")

    print(f"Warning: Could not determine port for domain {domain}, using default")
    return base_port


def extract_body_text(xml_content):
    try:
        root = ET.fromstring(xml_content)
        body = root.find(".//body")
        if body is not None:
            body_html = ET.tostring(body, encoding="unicode")
            soup = BeautifulSoup(body_html, "html.parser")
            return soup.get_text(separator=" ", strip=True)
    except ET.ParseError as e:
        print(f"XML parsing error: {e}")
    return ""


def extract_title(xml_content):
    try:
        root = ET.fromstring(xml_content)
        title = root.find(".//article-title")
        if title is not None:
            if title.text is None:
                return "Untitled"
            return title.text.strip()
    except ET.ParseError as e:
        print(f"XML parsing error while extracting title: {e}")
    return "Untitled"


def fetch_articles(query, count=10):
    print(f"Searching for '{query}' articles...")

    search_url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pmc&term={query}&retmax={count}&retmode=json"

    search_response = requests.get(search_url)
    if search_response.status_code != 200:
        print(f"Error searching PubMed: {search_response.status_code}")
        return []

    search_data = search_response.json()
    article_ids = search_data["esearchresult"]["idlist"]
    print(f"Found {len(article_ids)} articles")

    articles = []

    for i, pmc_id in enumerate(article_ids):
        print(f"Fetching article {i + 1}/{len(article_ids)}: PMC{pmc_id}")
        fetch_url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pmc&id={pmc_id}&retmode=xml"
        fetch_response = requests.get(fetch_url)

        if fetch_response.status_code == 200:
            body_text = extract_body_text(fetch_response.content)
            title = extract_title(fetch_response.content)
            if body_text:
                articles.append(
                    {
                        "id": pmc_id,
                        "text": body_text,
                        "title": title,
                        "source": f"PMC{pmc_id}",
                    }
                )
            else:
                print(f"No text extracted from article PMC{pmc_id}")
        else:
            print(f"Error fetching article PMC{pmc_id}: {fetch_response.status_code}")

    return articles


def split_into_sentences(text):
    # Handle common abbreviations to avoid splitting incorrectly
    # Replace common abbreviations with a temporary placeholder
    common_abbr = [
        "Dr.",
        "Mr.",
        "Mrs.",
        "Ms.",
        "Ph.D.",
        "e.g.",
        "i.e.",
        "etc.",
        "vs.",
        "Fig.",
        "Eq.",
    ]
    placeholders = {abbr: f"__{abbr.replace('.', '')}__" for abbr in common_abbr}

    for abbr, placeholder in placeholders.items():
        text = text.replace(abbr, placeholder)

    # Split by periods followed by space and uppercase letter
    # This regex looks for ". " followed by an uppercase letter or digit
    sentences = re.split(r"(?<=\. )(?=[A-Z0-9])", text)

    # Restore abbreviations
    for abbr, placeholder in placeholders.items():
        sentences = [s.replace(placeholder, abbr) for s in sentences]

    # Clean up sentences
    sentences = [s.strip() for s in sentences if s.strip()]

    return sentences


def estimate_token_count(text):
    return len(text.split())


def chunk_text(text, target_chunk_size=CHUNK_SIZE, sentence_overlap=OVERLAP):
    if estimate_token_count(text) <= target_chunk_size:
        return [text]

    sentences = split_into_sentences(text)

    if len(sentences) <= sentence_overlap + 1:
        return [text]

    chunks = []
    current_chunk = []
    current_size = 0

    for i, sentence in enumerate(sentences):
        sentence_size = estimate_token_count(sentence)

        # If a single sentence exceeds target size, we still keep it as one unit
        # but we might want to split very long sentences in a more sophisticated version
        # If adding this sentence would exceed our target size and we have content,
        # then finish the current chunk and start a new one
        if current_size + sentence_size > target_chunk_size and current_chunk:
            chunks.append(" ".join(current_chunk))
            # Keep the last 'sentence_overlap' sentences for context continuity
            current_chunk = (
                current_chunk[-sentence_overlap:] if sentence_overlap > 0 else []
            )
            current_size = estimate_token_count(" ".join(current_chunk))

        # Add the current sentence to the chunk
        current_chunk.append(sentence)
        current_size += sentence_size

    # Don't forget the last chunk if it has content
    if current_chunk:
        chunks.append(" ".join(current_chunk))

    return chunks


def main():
    args = parse_arguments()

    if not args.port:
        args.port = get_domain_port(args.domain)

    print(f"Connecting to Qdrant at {args.host}:{args.port} for domain '{args.domain}'")

    # Initialize Qdrant client
    client = QdrantClient(host=args.host, port=args.port)

    # Initialize embedding model
    print("Loading embedding model...")
    model = SentenceTransformer("all-MiniLM-L6-v2")
    vector_size = model.get_sentence_embedding_dimension()

    if vector_size is None:
        print("Error: Could not determine embedding dimension")
        return

    # Create collection if it doesn't exist
    collection_name = f"{args.domain}_docs"
    print(f"Ensuring collection '{collection_name}' exists...")

    try:
        collections = client.get_collections().collections
        collection_exists = any(col.name == collection_name for col in collections)

        if not collection_exists:
            print(f"Creating new collection: {collection_name}")
            client.create_collection(
                collection_name=collection_name,
                vectors_config=models.VectorParams(
                    size=vector_size, distance=models.Distance.COSINE
                ),
            )
    except Exception as e:
        print(f"Error creating collection: {e}")
        return

    # Fetch articles
    articles = fetch_articles(args.query, args.count)
    print(f"Processing {len(articles)} articles...")

    # Process each article
    total_chunks = 0
    for article in articles:
        # Chunk the article text
        chunks = chunk_text(article["text"], args.chunk_size, args.overlap)
        chunk_count = len(chunks)
        total_chunks += chunk_count
        print(f"Article {article['id']} divided into {chunk_count} chunks")

        for i, chunk in enumerate(chunks):
            # Create embedding for each chunk
            embedding = model.encode(chunk)

            # Create metadata
            metadata = {
                "title": article["title"],
                "source": article["source"],
                "domain": args.domain,
                "query": args.query,
                "chunk_index": i,
                "total_chunks": chunk_count,
                "text_preview": chunk[:200] + "..." if len(chunk) > 200 else chunk,
                "token_estimate": estimate_token_count(chunk),
            }

            # Create point
            point_id = str(uuid.uuid4())
            point = models.PointStruct(
                id=point_id, vector=embedding.tolist(), payload=metadata
            )

            # Upload point
            client.upsert(collection_name=collection_name, points=[point])

    print(
        f"Ingestion complete! Added {len(articles)} articles ({total_chunks} chunks) to {collection_name}"
    )


if __name__ == "__main__":
    main()
