from enum import Enum
from pydantic import BaseModel
from .utilities import (
    logger,
    PromptTemplate,
    prepare_prompt,
    llm,
    producer,
    diseases,
    redis_client,
    chat_history_url,
)
from datetime import datetime
from typing import List
import httpx
import json


REASONING_ATTEMPTS = 5


class ConversationItem(BaseModel):
    question: str
    answer: str
    timestamp: datetime = datetime.now()


class ConversationModel(BaseModel):
    username: str
    created_at: datetime
    conversation: List[ConversationItem]


class ChatbotQuery(BaseModel):
    user_id: str
    query: str


class PlanningException(Exception):
    pass


class ReasoningException(PlanningException):
    pass


class ActingException(PlanningException):
    pass


class Grade(Enum):
    EASY = "EASY"
    MEDIUM = "MEDIUM"
    HARD = "HARD"


class DiseaseSpecificQuestion(BaseModel):
    disease: str
    question: str


class ReasoningOutcome(BaseModel):
    classification: Grade
    diseases: List[DiseaseSpecificQuestion]
    reasoning: str


class ProducerMessage(BaseModel):
    user_id: str
    original_query: str
    rag_query: str
    stream: bool
    number: int
    total: int


async def reason(chatbot_query: ChatbotQuery) -> ReasoningOutcome:
    params = {"query": chatbot_query.query, "diseases": diseases}
    prompt = prepare_prompt(template=PromptTemplate.PLANNING.value, **params)
    for i in range(REASONING_ATTEMPTS):
        try:
            logger.info(f"Reasoning attempt #{i + 1}/{REASONING_ATTEMPTS}")
            generate_response = llm.generate(model="llama3.3:latest", prompt=prompt)
            logger.info(generate_response)
            return ReasoningOutcome.model_validate_json(generate_response.response)
        except Exception as e:
            logger.error(f"Error on attempt #{i + 1}/{REASONING_ATTEMPTS}: {e}")
    raise ReasoningException(f"Could not reason after {REASONING_ATTEMPTS} attempt(s)")


async def act(outcome: ReasoningOutcome, chatbot_query: ChatbotQuery) -> None:
    def create_producer_message(
        rag_query: str, stream: bool, number: int, total: int
    ) -> ProducerMessage:
        return ProducerMessage(
            user_id=chatbot_query.user_id,
            original_query=chatbot_query.query,
            rag_query=rag_query,
            stream=stream,
            number=number,
            total=total,
        )

    try:
        match outcome.classification:
            case Grade.EASY:
                async with httpx.AsyncClient() as client:
                    context = await client.get(
                        f"{chat_history_url}/{chatbot_query.user_id}",
                    )
                    context.raise_for_status()
                    context = ConversationModel.model_validate_json(context.json())
                await generate_answer(chatbot_query, context.conversation)
            case Grade.MEDIUM:
                msg = create_producer_message(
                    rag_query=chatbot_query.query, stream=True, number=1, total=1
                )
                producer.send(topic=outcome.diseases[0], value=msg.model_dump())
            case Grade.HARD:
                for i, dsq in enumerate(outcome.diseases, start=1):
                    msg = create_producer_message(
                        rag_query=dsq.question,
                        stream=False,
                        number=i,
                        total=len(outcome.diseases),
                    )
                    producer.send(topic=dsq.disease, value=msg.model_dump())
    except Exception as e:
        logger.error(f"Error while trying to perform an action: {e}")
        raise ActingException("Action not performed")


async def generate_answer(
    chatbot_query: ChatbotQuery, conversation: List[ConversationItem]
) -> None:
    params = {
        "query": chatbot_query.query,
        "context": json.dumps([item.model_dump() for item in conversation], indent=4),
    }
    prompt = prepare_prompt(template=PromptTemplate.EASY_QUERIES.value, **params)
    stream = llm.generate(model="llama3.3:latest", prompt=prompt, stream=True)
    for chunk in stream:
        logger.info(chunk.response)
        entry_id = redis_client.xadd(
            name=chatbot_query.user_id,
            fields={
                "query": chatbot_query.query,
                "response": chunk.response,
                "done": str(chunk.done),
            },
        )
        logger.info(f"Entry added with ID: {entry_id}")
