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
)
from typing import List


REASONING_ATTEMPTS = 5


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
    def create_producer_message(rag_query: str, stream: bool) -> ProducerMessage:
        return ProducerMessage(
            user_id=chatbot_query.user_id,
            original_query=chatbot_query.query,
            rag_query=rag_query,
            stream=stream,
        )

    try:
        match outcome.classification:
            case Grade.EASY:
                await answer_immediately(chatbot_query)
            case Grade.MEDIUM:
                msg = create_producer_message(
                    rag_query=chatbot_query.query, stream=True
                )
                producer.send(topic=outcome.diseases[0], value=msg.model_dump())
            case Grade.HARD:
                for dsq in outcome.diseases:
                    msg = create_producer_message(rag_query=dsq.question, stream=False)
                    producer.send(topic=dsq.disease, value=msg.model_dump())
    except Exception as e:
        logger.error(f"Error while trying to perform an action: {e}")
        raise ActingException("Action not performed")


async def answer_immediately(chatbot_query: ChatbotQuery) -> None:
    # ! TODO: create prompt template
    stream = llm.generate(
        model="llama3.3:latest", prompt=chatbot_query.query, stream=True
    )
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
