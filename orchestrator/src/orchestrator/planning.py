from enum import Enum
from pydantic import BaseModel
from .configurations import (
    logger,
    get_diseases_from_config_file,
    PromptTemplate,
    prepare_prompt,
    CHAT_HISTORY_URL,
)
from .exceptions import ReasoningException, ActingException
from datetime import datetime
from typing import List
from groq import AsyncGroq
from groq.types.chat import ChatCompletionMessageParam
from aiokafka import AIOKafkaProducer
import redis.asyncio as redis
import httpx
import uuid

REASONING_ATTEMPTS = 5

diseases = get_diseases_from_config_file()


class ChatbotQuery(BaseModel):
    user_id: str
    query: str
    plain_text: bool = False


class ConversationItem(BaseModel):
    question: str
    answer: str
    timestamp: datetime = datetime.now()


class ConversationModel(BaseModel):
    username: str
    created_at: datetime
    conversation: List[ConversationItem]


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


class RAGModuleMessage(BaseModel):
    user_id: str
    query_id: str
    original_query: str
    rag_query: str
    stream: bool
    number: int
    total: int
    plain_text: bool = False


def create_rag_module_message(
    chatbot_query: ChatbotQuery,
    query_id: str,
    rag_query: str,
    stream: bool,
    number: int,
    total: int,
) -> RAGModuleMessage:
    return RAGModuleMessage(
        user_id=chatbot_query.user_id,
        query_id=query_id,
        original_query=chatbot_query.query,
        rag_query=rag_query,
        stream=stream,
        number=number,
        total=total,
        plain_text=chatbot_query.plain_text,
    )


async def reason(chatbot_query: ChatbotQuery, llm: AsyncGroq) -> ReasoningOutcome:
    logger.info(f"Diseases: {diseases}")
    prompt = prepare_prompt(
        template=PromptTemplate.PLANNING.value, **{"diseases": diseases}
    )
    for i in range(REASONING_ATTEMPTS):
        try:
            logger.info(f"Reasoning attempt #{i + 1}/{REASONING_ATTEMPTS}")
            chat_completion = await llm.chat.completions.create(
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": chatbot_query.query},
                ],
                model="llama-3.3-70b-versatile",
                stream=False,
            )
            content = chat_completion.choices[0].message.content
            logger.info(content)
            return ReasoningOutcome.model_validate_json(str(content))
        except Exception as e:
            logger.error(f"Error on attempt #{i + 1}/{REASONING_ATTEMPTS}: {e}")
    raise ReasoningException(f"Could not reason after {REASONING_ATTEMPTS} attempt(s)")


async def act(
    outcome: ReasoningOutcome,
    chatbot_query: ChatbotQuery,
    kafka_producer: AIOKafkaProducer,
    redis_client: redis.Redis,
    llm: AsyncGroq,
) -> None:
    try:
        match outcome.classification:
            case Grade.EASY:
                await answer(chatbot_query, llm, redis_client)
            case Grade.MEDIUM:
                await ask_single_doctor(
                    chatbot_query, outcome.diseases[0].disease, kafka_producer
                )
            case Grade.HARD:
                await ask_many_doctors(chatbot_query, outcome.diseases, kafka_producer)
    except Exception as e:
        logger.error(f"Error while trying to perform an action: {e}")
        raise ActingException("Action not performed")


async def answer(
    chatbot_query: ChatbotQuery, llm: AsyncGroq, redis_client: redis.Redis
) -> None:
    conversation = await fetch_chat_history_for_user(chatbot_query.user_id)
    await generate_answer(chatbot_query, conversation, llm, redis_client)


async def ask_single_doctor(
    chatbot_query: ChatbotQuery, disease: str, kafka_producer: AIOKafkaProducer
) -> None:
    query_id = str(uuid.uuid4())
    msg = create_rag_module_message(
        chatbot_query, query_id, chatbot_query.query, stream=True, number=1, total=1
    )
    topic = f"rag-module-{disease}"
    logger.info(f"Sending message to {topic}: {msg.model_dump_json(indent=4)}")
    await kafka_producer.send_and_wait(topic=topic, value=msg.model_dump())


async def ask_many_doctors(
    chatbot_query: ChatbotQuery,
    questions: List[DiseaseSpecificQuestion],
    kafka_producer: AIOKafkaProducer,
) -> None:
    query_id = str(uuid.uuid4())
    for i, dsq in enumerate(questions, start=1):
        topic = f"rag-module-{dsq.disease}"
        msg = create_rag_module_message(
            chatbot_query,
            query_id,
            dsq.question,
            stream=False,
            number=i,
            total=len(questions),
        )
        logger.info(f"Sending message to {topic}: {msg.model_dump_json(indent=4)}")
        await kafka_producer.send_and_wait(topic=topic, value=msg.model_dump())


async def fetch_chat_history_for_user(user_id: str) -> List[ConversationItem]:
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{CHAT_HISTORY_URL}/{user_id}")
        response.raise_for_status()
        model = ConversationModel.model_validate(response.json())
    return model.conversation


async def generate_answer(
    chatbot_query: ChatbotQuery,
    conversation: List[ConversationItem],
    llm: AsyncGroq,
    redis_client: redis.Redis,
) -> None:
    if chatbot_query.plain_text:
        output_format = "Please provide your response in plain text format without any Markdown formatting."
    else:
        output_format = "Structure your answer with appropriate headings and sections."

    system_prompt = prepare_prompt(
        template=PromptTemplate.EASY_QUERIES.value, **{"output_format": output_format}
    )

    messages: List[ChatCompletionMessageParam] = [
        {"role": "system", "content": system_prompt}
    ]
    for qap in conversation:
        messages.extend(
            [
                {"role": "user", "content": qap.question},
                {"role": "assistant", "content": qap.answer},
            ]
        )
    messages.append({"role": "user", "content": chatbot_query.query})

    logger.info(f"Messages\n\n: {messages}")
    stream = await llm.chat.completions.create(
        messages=messages,
        model="llama-3.3-70b-versatile",
        stream=True,
    )
    async for chunk in stream:
        content = chunk.choices[0].delta.content
        logger.info(content)
        await redis_client.xadd(
            name=chatbot_query.user_id,
            fields={
                "query": chatbot_query.query,
                "response": str(content),
                "done": str(
                    chunk.choices[0].finish_reason
                ),  # finish_reason will be equal to "stop" when stream is done
            },
        )
