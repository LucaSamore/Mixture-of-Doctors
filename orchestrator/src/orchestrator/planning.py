from enum import Enum
from pydantic import BaseModel
from .configurations import (
    logger,
    get_diseases_from_config_file,
    PromptTemplate,
    prepare_prompt,
    llm_groq,
    kafka_producer,
    redis_client,
    chat_history_url,
)
from .exceptions import ReasoningException, ActingException
from datetime import datetime
from typing import List
import httpx
import json


REASONING_ATTEMPTS = 5

diseases = get_diseases_from_config_file()


class ChatbotQuery(BaseModel):
    user_id: str
    query: str


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
    original_query: str
    rag_query: str
    stream: bool
    number: int
    total: int


def create_rag_module_message(
    chatbot_query: ChatbotQuery, rag_query: str, stream: bool, number: int, total: int
) -> RAGModuleMessage:
    return RAGModuleMessage(
        user_id=chatbot_query.user_id,
        original_query=chatbot_query.query,
        rag_query=rag_query,
        stream=stream,
        number=number,
        total=total,
    )


async def reason(chatbot_query: ChatbotQuery) -> ReasoningOutcome:
    logger.info(f"Diseases: {diseases}")
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
    try:
        match outcome.classification:
            case Grade.EASY:
                await answer(chatbot_query)
            case Grade.MEDIUM:
                await ask_single_doctor(chatbot_query, outcome.diseases[0].disease)
            case Grade.HARD:
                await ask_many_doctors(chatbot_query, outcome.diseases)
    except Exception as e:
        logger.error(f"Error while trying to perform an action: {e}")
        raise ActingException("Action not performed")


async def answer(chatbot_query: ChatbotQuery) -> None:
    conversation = await fetch_chat_history_for_user(chatbot_query.user_id)
    await generate_answer(chatbot_query, conversation)


async def ask_single_doctor(chatbot_query: ChatbotQuery, disease: str) -> None:
    msg = create_rag_module_message(
        chatbot_query, chatbot_query.query, stream=True, number=1, total=1
    )
    topic = f"rag-module-{disease}"
    logger.info(f"Sending message to {topic}: {msg.model_dump_json(indent=4)}")
    kafka_producer.send(topic=topic, value=msg.model_dump())


async def ask_many_doctors(
    chatbot_query: ChatbotQuery, questions: List[DiseaseSpecificQuestion]
) -> None:
    for i, dsq in enumerate(questions, start=1):
        topic = f"rag-module-{dsq.disease}"
        msg = create_rag_module_message(
            chatbot_query, dsq.question, stream=False, number=i, total=len(diseases) - 1
        )
        logger.info(f"Sending message to {topic}: {msg.model_dump_json(indent=4)}")
        kafka_producer.send(topic=topic, value=msg.model_dump())


async def fetch_chat_history_for_user(user_id: str) -> List[ConversationItem]:
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{chat_history_url}/{user_id}")
        response.raise_for_status()
        model = ConversationModel.model_validate(response.json())
    return model.conversation


async def generate_answer(
    chatbot_query: ChatbotQuery, conversation: List[ConversationItem]
) -> None:
    context = json.dumps([item.model_dump_json() for item in conversation], indent=4)
    logger.info(f"Context: {context}")
    params = {"query": chatbot_query.query, "context": context}
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
        redis_client.xadd(
            name=chatbot_query.user_id,
            fields={
                "query": chatbot_query.query,
                "response": str(content),
                "done": str(
                    chunk.choices[0].finish_reason
                ),  # finish_reason will be equal to "stop" when stream is done
            },
        )
