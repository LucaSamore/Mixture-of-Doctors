from .doctors import DiseaseQuestions, get_diseases
from enum import Enum
from pydantic import BaseModel, ValidationError
from shared.llm import llm, build_prompt
from shared.broker import producer
from .utilities import logger, PromptTemplate


class Grade(Enum):
    EASY = "EASY"
    MEDIUM = "MEDIUM"
    HARD = "HARD"


class ReasoningOutcome(BaseModel):
    classification: Grade
    diseases: DiseaseQuestions
    reasoning: str


def reason(query: str) -> ReasoningOutcome | None:
    params = {"query": query, "diseases": get_diseases()}
    prompt = build_prompt(template=PromptTemplate.PLANNING.value, **params)
    for _ in range(5):
        res = llm.generate(model="llama3.3:latest", prompt=prompt)
        logger.info(res.response)
        try:
            return ReasoningOutcome.model_validate_json(res.response)
        except ValidationError as ve:
            logger.error(ve)
    return None


def act(outcome: ReasoningOutcome, query: str) -> None:
    match outcome.classification:
        case Grade.EASY:
            answer_directly(query)
        case Grade.MEDIUM:
            disease_question = outcome.diseases[0]
            producer.send(
                disease_question.disease,
                { "test": disease_question.question }
            )
        case Grade.HARD:
            for disease_question in outcome.diseases:
                producer.send(
                    disease_question.disease,
                    { "test": disease_question.question }
                )


def answer_directly(query: str) -> None:
    # generates a response for easy queries
    # prepare prompt for generating the response
    # make the LLM call -- streaming
    # send the stream to the channel
    pass
