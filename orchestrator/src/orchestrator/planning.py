from .doctors import DiseaseQuestions, get_diseases
from enum import Enum
from pydantic import BaseModel, ValidationError
from shared.llm import llm, build_prompt
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


def act(outcome: ReasoningOutcome) -> None:
    # pattern match against the outcome
    # call the appropriate function, i.e. make tool call
    print("Acting...")
    pass


def answer_directly(query: str) -> None:
    # generates a response for easy queries
    # prepare prompt for generating the response
    # make the LLM call -- streaming
    # send the stream to the channel
    pass
