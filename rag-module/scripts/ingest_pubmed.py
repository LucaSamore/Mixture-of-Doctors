import argparse
import requests
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.http import models
import uuid
import json
import nltk

CHUNK_SIZE = 1000
OVERLAP = 200  # Overlap between chunks


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


def chunk_text(text, chunk_size=CHUNK_SIZE, overlap=OVERLAP):
    try:
        nltk.data.find("tokenizers/punkt_tab")
    except LookupError:
        nltk.download("punkt_tab")

    sentences = nltk.sent_tokenize(text)
    chunks = []
    current_chunk = ""

    for sentence in sentences:
        if len(current_chunk) + len(sentence) > chunk_size and current_chunk:
            chunks.append(current_chunk)
            overlap_text = (
                current_chunk[-overlap:] if len(current_chunk) > overlap else ""
            )
            current_chunk = overlap_text

        current_chunk += sentence + " "

    if current_chunk:
        chunks.append(current_chunk)

    return chunks


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
            if body_text:
                articles.append(
                    {"id": pmc_id, "text": body_text, "source": f"PMC{pmc_id}"}
                )
            else:
                print(f"No text extracted from article PMC{pmc_id}")
        else:
            print(f"Error fetching article PMC{pmc_id}: {fetch_response.status_code}")

    return articles


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

    total_chunks = 0

    # Process each article
    for article in articles:
        # Split article into chunks
        text_chunks = chunk_text(article["text"])
        print(f"Article PMC{article['id']}: Split into {len(text_chunks)} chunks")

        # Create points for each chunk
        points = []
        for i, text_chunk in enumerate(text_chunks):
            point_id = str(uuid.uuid4())

            # Create embedding
            embedding = model.encode(text_chunk)

            # Create metadata
            metadata = {
                "source": article["source"],
                "chunk_index": i,
                "domain": args.domain,
                "query": args.query,
                "text": text_chunk[:200] + "...",  # Preview only
            }

            # Create point
            points.append(
                models.PointStruct(
                    id=point_id, vector=embedding.tolist(), payload=metadata
                )
            )

            # print(f"  Chunk {i + 1}: {textwrap.shorten(text_chunk, width=100)}")

        # Upload points in batches
        batch_size = 100
        for i in range(0, len(points), batch_size):
            batch = points[i : i + batch_size]
            client.upsert(collection_name=collection_name, points=batch)
            print(
                f"  Uploaded batch {i // batch_size + 1}/{(len(points) + batch_size - 1) // batch_size}"
            )

        total_chunks += len(text_chunks)

    print(
        f"Ingestion complete! Added {total_chunks} chunks from {len(articles)} articles to {collection_name}"
    )


if __name__ == "__main__":
    main()
