from dataclasses import dataclass
from .doctors import DiseaseQuestions, get_diseases
from enum import Enum
from dotenv import load_dotenv
from ollama import Client
from pydantic import BaseModel, ValidationError
import os
import string

load_dotenv()

host = os.getenv("CLUSTER_HOST")
port = (lambda p: int(p) if p else None)(os.getenv("CLUSTER_PORT"))

model = "llama3.3:latest"
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


def build_prompt(template: str, **kwargs) -> str:
    with open(template, "r") as f:
        template = f.read()
    return string.Template(template).substitute(kwargs)


def reason(query: str) -> ReasoningOutcome | None:
    params = {"query": query, "diseases": get_diseases()}
    prompt = build_prompt(
        template="./orchestrator/src/orchestrator/prompts/planning.md", **params
    )
    for _ in range(5):
        res = llm.generate(model=model, prompt=prompt)
        print(res.response)
        try:
            outcome = ReasoningOutcome.model_validate_json(res.response)
            print(outcome.classification, outcome.diseases, outcome.reasoning)
            return outcome
        except ValidationError as ve:
            print(ve)
    return None


def act(outcome: ReasoningOutcome) -> None:
    # pattern match against the outcome
    # call the appropriate function, i.e. make tool call
    print("Acting...")
    pass


def answer_directly(query: Query) -> None:
    # generates a response for easy queries
    # prepare prompt for generating the response
    # make the LLM call -- streaming
    # send the stream to the channel
    pass
