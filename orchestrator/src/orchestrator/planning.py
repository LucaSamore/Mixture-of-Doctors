from dataclasses import dataclass
from pydantic import BaseModel, ValidationError
from ollama import Client
from enum import Enum
from dotenv import load_dotenv
from .doctors import DiseaseQuestions, get_diseases
import os
import string

load_dotenv()

host = os.getenv("CLUSTER_HOST")
port = (lambda p: int(p) if p else None)(os.getenv("CLUSTER_PORT"))

model = "llama3.3:latest"  # just for testing
llm = Client(host=f"http://{host}:{port}")


@dataclass(frozen=True)
class Query:
    question: str
    username: str


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

    with open("./orchestrator/src/orchestrator/prompts/planning.md", "r") as f:
        template = f.read()

    prompt = string.Template(template).substitute(params)
    res = llm.generate(model=model, prompt=prompt)
    print(res.response)

    try:
        outcome = ReasoningOutcome.model_validate_json(res.response)
        print(outcome.classification, outcome.diseases, outcome.reasoning)
        return outcome
    except ValidationError as ve:
        # ! TODO: iterate classification until a valid response is obtained
        # parsing the output may fail due to the llm response wrongly formatted
        print(ve)
        return None


def act(outcome: ReasoningOutcome) -> None:
    # pattern match against the outcome
    # call the appropriate function, i.e. make tool call
    pass


def answer_directly(query: Query) -> None:
    # generates a response for easy queries
    # prepare prompt for generating the response
    # make the LLM call -- streaming
    # send the stream to the channel
    pass


if __name__ == "__main__":
    question = "What is the cause of diabetes and hypertension?"
    reason(question)
