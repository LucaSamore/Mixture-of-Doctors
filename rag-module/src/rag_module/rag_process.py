from .kafka_client import RAGModuleMessage
from .utilities import (
    RAGClients,
    DateTimeEncoder,
    fetch_chat_history_for_user,
    prepare_prompt,
)
from loguru import logger
from qdrant_client.http.models import ScoredPoint, QueryResponse
from typing import List, TypeAlias
import asyncio
import os
import json


PROMPT_FILE = "/app/prompts/rag_module.md"
DOMAIN = os.getenv("RAG_DOMAIN")

Query: TypeAlias = str
Prompt: TypeAlias = str


class RAGProcessor:
    def __init__(self, clients: RAGClients):
        self.clients = clients

    async def process_incoming_query(self) -> None:
        message = await self.clients.kafka_client.get_message_from_queue()
        if message is not None:
            logger.info(f"Received message: {message}")
            try:
                context = await self._retrieve(message.rag_query)
                prompt = await self._augment(
                    context, message.rag_query, message.user_id
                )
                await self._generate(prompt, message)
            except Exception as e:
                logger.error(f"Error processing message: {e}")

    async def _retrieve(self, query: Query) -> List[dict]:
        logger.info(f"Retrieving context for query: {query}")
        query_vector = self.clients.embedding_model.encode(query).tolist()
        logger.info("Doing vector search...")
        search_result = await self.clients.qdrant_client.query_points(
            collection_name=f"{DOMAIN}_docs", query=query_vector, limit=5
        )

        logger.info(f"Retrieved search results: {search_result}")

        results = []
        if isinstance(search_result, QueryResponse) and hasattr(
            search_result, "points"
        ):
            scored_points = search_result.points

            for point in scored_points:
                if isinstance(point, ScoredPoint) and hasattr(point, "payload"):
                    results.append(point.payload)
                else:
                    logger.warning(f"Skipping point without payload: {point}")

            logger.info(f"Extracted {len(results)} payloads from search results")
        else:
            logger.warning(f"Unexpected search_result format: {search_result}")

        return results

    async def _augment(
        self, embeddings: List[dict], query: Query, user_id: str
    ) -> Prompt:
        conversation = await fetch_chat_history_for_user(user_id)

        conversation_data = [item.model_dump() for item in conversation]
        context = json.dumps(conversation_data, indent=4, cls=DateTimeEncoder)
        logger.info(f"Context: {context}")

        extracted_embeddings = []
        for payload in embeddings:
            if isinstance(payload, dict):
                extracted_embeddings.append(
                    {
                        "title": payload.get("title", ""),
                        "source": payload.get("source", ""),
                        "text": payload.get("text", ""),
                    }
                )
            else:
                logger.warning(
                    f"Skipping payload with unexpected type: {type(payload)}"
                )

        embeddings_context = json.dumps(
            extracted_embeddings, indent=4, cls=DateTimeEncoder
        )
        logger.info(f"Embeddings Context: {embeddings_context}")

        combined_context = (
            f"Chat History:\n{context}\n\nEmbeddings:\n{embeddings_context}"
        )
        params = {"query": query, "context": combined_context}
        return prepare_prompt(template=PROMPT_FILE, **params)

    async def _generate(
        self, prompt: Prompt, incoming_message: RAGModuleMessage
    ) -> None:
        logger.info(f"Generating response for query:\n{incoming_message}")

        if incoming_message.total == 1:
            await self._handle_stream_response(prompt, incoming_message)
        else:
            await self._handle_batch_response(prompt, incoming_message)

    async def _handle_stream_response(
        self, prompt: Prompt, incoming_message: RAGModuleMessage
    ) -> None:
        stream = await self.clients.llm_groq_client.chat.completions.create(
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": incoming_message.rag_query},
            ],
            model="llama-3.3-70b-versatile",
            stream=True,
        )
        async for chunk in stream:
            content = chunk.choices[0].delta.content
            self.clients.redis_client.xadd(
                name=incoming_message.user_id,
                fields={
                    "query": incoming_message.original_query,
                    "response": str(content),
                    "done": str(chunk.choices[0].finish_reason),
                },
            )

    async def _handle_batch_response(
        self, prompt: Prompt, incoming_message: RAGModuleMessage
    ) -> None:
        chat_completion = await self.clients.llm_groq_client.chat.completions.create(
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": incoming_message.rag_query},
            ],
            model="llama-3.3-70b-versatile",
            max_completion_tokens=1024,
            stream=False,
        )
        await self.clients.kafka_client.send_message_to_queue(
            chat_completion, incoming_message
        )


async def main():
    logger.info(f"RAG process initialized with domain: {DOMAIN}")
    logger.info("Setting up clients...")
    clients = await RAGClients.create()
    logger.info("Clients initialized successfully")
    processor = RAGProcessor(clients)
    logger.info("Waiting for incoming messages...")
    while True:
        try:
            await processor.process_incoming_query()
            await asyncio.sleep(0.1)
        except Exception as e:
            logger.error(f"Error in main processing loop: {e}")
            await asyncio.sleep(1)


if __name__ == "__main__":
    asyncio.run(main())
