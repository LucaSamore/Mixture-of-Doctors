from enum import Enum
from pydantic import BaseModel
from .configurations import (
    logger,
    PromptTemplate,
    prepare_prompt,
    llm_groq,
    kafka_producer,
    diseases,
    redis_client,
    chat_history_url,
)
from .exceptions import ReasoningException, ActingException
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
            chat_completion = llm_groq.chat.completions.create(
                messages=[{"role": "system", "content": prompt}],
                model="llama-3.3-70b-versatile",
                stream=False,
            )
            content = chat_completion.choices[0].message.content
            logger.info(content)
            return ReasoningOutcome.model_validate_json(str(content))
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
                    response = await client.get(
                        f"{chat_history_url}/{chatbot_query.user_id}",
                    )
                    context = response.json()
                    data = ConversationModel.model_validate(context)
                await generate_answer(chatbot_query, data.conversation)
            case Grade.MEDIUM:
                msg = create_producer_message(
                    rag_query=chatbot_query.query, stream=True, number=1, total=1
                )
                kafka_producer.send(
                    topic=f"rag-module-{outcome.diseases[0].disease}",
                    value=msg.model_dump(),
                )
            case Grade.HARD:
                for i, dsq in enumerate(outcome.diseases, start=1):
                    msg = create_producer_message(
                        rag_query=dsq.question,
                        stream=False,
                        number=i,
                        total=len(outcome.diseases),
                    )
                    kafka_producer.send(
                        topic=f"rag-module-{dsq.disease}", value=msg.model_dump()
                    )
    except Exception as e:
        logger.error(f"Error while trying to perform an action: {e}")
        raise ActingException("Action not performed")


async def generate_answer(
    chatbot_query: ChatbotQuery, conversation: List[ConversationItem]
) -> None:
    context = json.dumps([item.model_dump_json() for item in conversation], indent=4)
    logger.info(context)
    params = {
        "query": chatbot_query.query,
        "context": context,
    }
    prompt = prepare_prompt(template=PromptTemplate.EASY_QUERIES.value, **params)
    stream = llm_groq.chat.completions.create(
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": chatbot_query.query},
        ],
        model="llama-3.3-70b-versatile",
        stream=True,
    )
    for chunk in stream:
        content = chunk.choices[0].delta.content
        logger.info(content)
        entry_id = redis_client.xadd(
            name=chatbot_query.user_id,
            fields={
                "query": chatbot_query.query,
                "response": str(content),
                "done": str(chunk.choices[0].finish_reason),
            },
        )
        # finish_reason will be equal to "stop"
        logger.info(f"Entry added with ID: {entry_id}")
