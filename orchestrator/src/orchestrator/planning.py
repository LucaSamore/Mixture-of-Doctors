from enum import Enum
from pydantic import BaseModel
from .utilities import logger, PromptTemplate, prepare_prompt, llm, producer, diseases
from typing import List


REASONING_ATTEMPTS = 5


class PlanningException(Exception):
    pass


class ReasoningException(PlanningException):
    pass


class ActingException(PlanningException):
    pass


class DiseaseSpecificQuestion(BaseModel):
    disease: str
    question: str


class Grade(Enum):
    EASY = "EASY"
    MEDIUM = "MEDIUM"
    HARD = "HARD"


class ReasoningOutcome(BaseModel):
    classification: Grade
    diseases: List[DiseaseSpecificQuestion]
    reasoning: str


async def reason(query: str) -> ReasoningOutcome:
    params = {"query": query, "diseases": diseases}
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


async def act(outcome: ReasoningOutcome, query: str) -> None:
    try:
        match outcome.classification:
            case Grade.EASY:
                answer_immediately(query)
            case Grade.MEDIUM:
                dsq: DiseaseSpecificQuestion = outcome.diseases[0]
                producer.send(dsq.disease, {"test": dsq.question})
            case Grade.HARD:
                for dsq in outcome.diseases:
                    producer.send(dsq.disease, {"test": dsq.question})
    except Exception as e:
        logger.error(f"Error while trying to perform an action: {e}")
        raise ActingException("Action not performed")


def answer_immediately(_: str) -> None:
    raise NotImplementedError("Immediate answering not implemented yet")
