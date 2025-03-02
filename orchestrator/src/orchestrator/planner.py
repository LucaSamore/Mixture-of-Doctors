from dataclasses import dataclass
from pydantic import BaseModel
from ollama import Client
from typing import List
from enum import Enum
from dotenv import load_dotenv
import os

load_dotenv()

host = os.getenv("CLUSTER_HOST")
port = (lambda p: int(p) if p else None)(os.getenv("CLUSTER_PORT"))

llm = Client(host=f"http://{host}:{port}")

model = "llama3.3:latest"


def test_llm_call() -> None:
    res = llm.generate(model=model, prompt="Hello, how are you?")
    print(res)


action_template = ...


@dataclass(frozen=True)
class Query:
    question: str
    username: str
    # other metadata...


class Grade(Enum):
    EASY = "EASY"
    MEDIUM = "MEDIUM"
    HARD = "HARD"


class Classification(BaseModel):
    classification: Grade
    diseases: List[str]
    reasoning: str


# this is the LLM response containing the decision to make
class Action(BaseModel):
    ...
    # it contains username, query, grade, tool(s) to call...


def get_diseases() -> List[str]:
    # get diseases from configuration
    return ["diabetes", "malaria", "hypertension"]


def classify_query(query: Query) -> Grade | None:
    # prepare prompt for query classification
    # make the LLM call -- no streaming
    # parse the output
    # return grade
    pass


def reason(query: Query, grade: Grade) -> None:
    # if query is easy -> answer_directly()
    # otherwise -> orchestrate()
    pass


def answer_directly(query: Query) -> None:
    # generate a response for easy queries
    # prepare prompt for generating the response
    # make the LLM call -- streaming
    # send the stream to the channel
    pass


def orchestrate(action: Action) -> None:
    """
    If query is medium -> publish query to appropriate topic
                                                                                            listen for response stream from queue
                                                                                            send response as stream to websocket (by calling message_user)

    If query is hard   -> publish each subquery to appropriate topic (subqueries are in the Action object)
                                                                                            listen for responses from queue -- not as streams
                                                                                            invoke Synthesizer with subresponses
                                                                                            send response as stream to websocket (by calling message_user))
    """
    pass


def fetch_user_chat_history(username: str) -> List[str]:
    # for the context
    ...


if __name__ == "__main__":
    test_llm_call()
