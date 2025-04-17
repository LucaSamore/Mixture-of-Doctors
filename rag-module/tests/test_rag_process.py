import pytest
import numpy as np
from unittest.mock import MagicMock, patch, AsyncMock
from src.rag_module.rag_process import (
    retrieve,
    augment,
    generate,
    prepare_prompt,
    fetch_chat_history_for_user,
)
from qdrant_client.http.models import ScoredPoint


class TestRagProcess:
    @patch("src.rag_module.rag_process.SentenceTransformer")
    def test_retrieve(self, mock_transformer, mock_qdrant_client):
        mock_model = MagicMock()
        mock_model.encode.return_value = np.array([0.1, 0.2, 0.3])
        mock_transformer.return_value = mock_model

        payload1 = {"title": "Doc 1", "source": "source1", "text": "Test content 1"}
        payload2 = {"title": "Doc 2", "source": "source2", "text": "Test content 2"}

        mock_hit1 = ScoredPoint(
            id=1, score=0.9, payload=payload1, vector=None, version=1
        )
        mock_hit2 = ScoredPoint(
            id=2, score=0.8, payload=payload2, vector=None, version=1
        )

        with patch("src.rag_module.rag_process.qdrant_client", mock_qdrant_client):
            mock_qdrant_client.search.return_value = [mock_hit1, mock_hit2]

            query = "Test query"
            results = retrieve(query)

            mock_model.encode.assert_called_once_with(query)
            mock_qdrant_client.search.assert_called_once()

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
                "src.rag_module.rag_process.fetch_chat_history_for_user",
                mock_fetch_history,
            ),
            patch("src.rag_module.rag_process.prepare_prompt") as mock_prepare_prompt,
        ):
            mock_prepare_prompt.return_value = "Mocked prompt"

            query = "What are the symptoms of multiple sclerosis?"
            user_id = "test_user_123"

            result = await augment(embeddings, query, user_id)

            mock_fetch_history.assert_awaited_once_with(user_id)
            assert mock_prepare_prompt.called
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

    @patch("src.rag_module.rag_process.llm_groq_client")
    @patch("src.rag_module.rag_process.redis_client")
    def test_generate_direct_to_redis(
        self, mock_redis_client, mock_groq_client, sample_rag_message
    ):
        incoming_message = sample_rag_message
        incoming_message.total = 1

        mock_stream = []
        mock_chunk1 = MagicMock()
        mock_chunk1.choices = [MagicMock()]
        mock_chunk1.choices[0].delta.content = "The first symptom of sclerosis"
        mock_chunk1.choices[0].finish_reason = None

        mock_chunk2 = MagicMock()
        mock_chunk2.choices = [MagicMock()]
        mock_chunk2.choices[0].delta.content = " multiple is often optic neuritis"
        mock_chunk2.choices[0].finish_reason = "stop"

        mock_stream.append(mock_chunk1)
        mock_stream.append(mock_chunk2)

        mock_groq_client.chat.completions.create.return_value = mock_stream

        prompt = "System prompt"
        generate(prompt, incoming_message)

        mock_groq_client.chat.completions.create.assert_called_once_with(
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": incoming_message.rag_query},
            ],
            model="llama-3.3-70b-versatile",
            stream=True,
        )

        assert mock_redis_client.xadd.call_count == 2

        mock_redis_client.xadd.assert_any_call(
            name=incoming_message.user_id,
            fields={
                "query": incoming_message.original_query,
                "response": str(mock_chunk1.choices[0].delta.content),
                "done": str(mock_chunk1.choices[0].finish_reason),
            },
        )

        mock_redis_client.xadd.assert_any_call(
            name=incoming_message.user_id,
            fields={
                "query": incoming_message.original_query,
                "response": str(mock_chunk2.choices[0].delta.content),
                "done": str(mock_chunk2.choices[0].finish_reason),
            },
        )

    @patch("src.rag_module.rag_process.llm_groq_client")
    @patch("src.rag_module.rag_process.kafka_client")
    def test_generate_to_kafka(
        self, mock_kafka_client, mock_groq_client, sample_rag_message
    ):
        incoming_message = sample_rag_message
        incoming_message.total = 5

        mock_stream = MagicMock()

        mock_groq_client.chat.completions.create.return_value = mock_stream

        prompt = "System prompt with context"
        generate(prompt, incoming_message)

        mock_groq_client.chat.completions.create.assert_called_once_with(
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": incoming_message.rag_query},
            ],
            model="llama-3.3-70b-versatile",
            stream=True,
        )

        mock_kafka_client.send_message_to_queue.assert_called_once_with(
            mock_stream, incoming_message
        )
