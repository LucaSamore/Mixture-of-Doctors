import pytest
import numpy as np
from unittest.mock import MagicMock, patch, AsyncMock
from rag_module.rag_process import RAGProcessor
from rag_module.utilities import prepare_prompt, fetch_chat_history_for_user
from qdrant_client.http.models import QueryResponse, ScoredPoint


class TestRagProcess:
    @pytest.mark.asyncio
    async def test_retrieve(self, mock_qdrant_client):
        # Mock RAGClients
        mock_clients = MagicMock()
        mock_clients.embedding_model.encode.return_value = np.array([0.1, 0.2, 0.3])
        mock_clients.qdrant_client = mock_qdrant_client

        payload1 = {"title": "Doc 1", "source": "source1", "text": "Test content 1"}
        payload2 = {"title": "Doc 2", "source": "source2", "text": "Test content 2"}

        mock_point1 = MagicMock(spec=ScoredPoint)
        mock_point1.payload = payload1

        mock_point2 = MagicMock(spec=ScoredPoint)
        mock_point2.payload = payload2

        mock_query_response = QueryResponse(points=[mock_point1, mock_point2])

        mock_qdrant_client.query_points = AsyncMock(return_value=mock_query_response)

        # Create RAGProcessor instance
        processor = RAGProcessor(mock_clients)

        query = "Test query"
        results = await processor._retrieve(query)

        mock_clients.embedding_model.encode.assert_called_once_with(query)
        mock_qdrant_client.query_points.assert_awaited_once()

        assert len(results) == 2
        assert results[0] == payload1
        assert results[1] == payload2

    @pytest.mark.asyncio
    async def test_augment(self, sample_conversation_items):
        embeddings = [
            {
                "title": "Doc 1",
                "source": "source1",
                "text": "Content about multiple sclerosis",
            },
            {
                "title": "Doc 2",
                "source": "source2",
                "text": "More content about symptoms",
            },
        ]

        mock_fetch_history = AsyncMock(return_value=sample_conversation_items)

        with (
            patch(
                "rag_module.rag_process.fetch_chat_history_for_user",
                mock_fetch_history,
            ),
            patch("rag_module.rag_process.prepare_prompt") as mock_prepare_prompt,
        ):
            mock_prepare_prompt.return_value = "Mocked prompt"

            # Mock RAGClients
            mock_clients = MagicMock()
            processor = RAGProcessor(mock_clients)

            user_id = "test_user_123"

            result = await processor._augment(embeddings, user_id, True)

            mock_fetch_history.assert_awaited_once_with(user_id)
            mock_prepare_prompt.assert_called_once()
            assert result == "Mocked prompt"

    def test_prepare_prompt(self):
        with patch("builtins.open", MagicMock()) as mock_open:
            mock_file = MagicMock()
            mock_file.read.return_value = "Response: ${query}\nContext: ${context}"
            mock_open.return_value.__enter__.return_value = mock_file

            result = prepare_prompt(
                "template.md", query="test query", context="test context"
            )

            mock_open.assert_called_once_with("template.md", "r")

            assert result == "Response: test query\nContext: test context"

    @pytest.mark.asyncio
    async def test_fetch_chat_history_for_user(self, sample_conversation_items):
        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()

            conversation_model = {
                "username": "test_user",
                "created_at": "2025-04-14T12:00:00",
                "conversation": [
                    item.model_dump() for item in sample_conversation_items
                ],
            }

            mock_response.json.return_value = conversation_model

            mock_client.return_value.__aenter__.return_value.get.return_value = (
                mock_response
            )

            user_id = "test_user_123"
            result = await fetch_chat_history_for_user(user_id)

            assert mock_client.called
            assert len(result) == len(sample_conversation_items)

    @pytest.mark.asyncio
    async def test_generate_direct_to_redis(self, sample_rag_message):
        incoming_message = sample_rag_message
        incoming_message.total = 1

        mock_stream = AsyncMock()

        mock_chunk1 = MagicMock()
        mock_chunk1.choices = [MagicMock()]
        mock_chunk1.choices[0].delta.content = "The first symptom of sclerosis"
        mock_chunk1.choices[0].finish_reason = None

        mock_chunk2 = MagicMock()
        mock_chunk2.choices = [MagicMock()]
        mock_chunk2.choices[0].delta.content = " multiple is often optic neuritis"
        mock_chunk2.choices[0].finish_reason = "stop"

        mock_stream.__aiter__.return_value = [mock_chunk1, mock_chunk2].__iter__()

        # Mock RAGClients
        mock_clients = MagicMock()
        mock_clients.llm_groq_client.chat.completions.create = AsyncMock(
            return_value=mock_stream
        )
        mock_clients.redis_client.xadd = AsyncMock()

        processor = RAGProcessor(mock_clients)

        prompt = "System prompt"
        await processor._generate(prompt, incoming_message)

        mock_clients.llm_groq_client.chat.completions.create.assert_awaited_once_with(
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": incoming_message.rag_query},
            ],
            model="llama-3.3-70b-versatile",
            stream=True,
        )

        assert mock_clients.redis_client.xadd.call_count == 2

        mock_clients.redis_client.xadd.assert_any_call(
            name=incoming_message.user_id,
            fields={
                "query": incoming_message.original_query,
                "response": str(mock_chunk1.choices[0].delta.content),
                "done": str(mock_chunk1.choices[0].finish_reason),
            },
        )

        mock_clients.redis_client.xadd.assert_any_call(
            name=incoming_message.user_id,
            fields={
                "query": incoming_message.original_query,
                "response": str(mock_chunk2.choices[0].delta.content),
                "done": str(mock_chunk2.choices[0].finish_reason),
            },
        )

    @pytest.mark.asyncio
    async def test_generate_to_kafka(self, sample_rag_message):
        incoming_message = sample_rag_message
        incoming_message.total = 5

        mock_completion = MagicMock()

        # Mock RAGClients
        mock_clients = MagicMock()
        mock_clients.llm_groq_client.chat.completions.create = AsyncMock(
            return_value=mock_completion
        )
        mock_clients.kafka_client.send_message_to_queue = AsyncMock()

        processor = RAGProcessor(mock_clients)

        prompt = "System prompt with context"
        await processor._generate(prompt, incoming_message)

        mock_clients.llm_groq_client.chat.completions.create.assert_awaited_once_with(
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": incoming_message.rag_query},
            ],
            model="llama-3.3-70b-versatile",
            max_completion_tokens=1024,
            stream=False,
        )

        mock_clients.kafka_client.send_message_to_queue.assert_called_once_with(
            mock_completion, incoming_message
        )
