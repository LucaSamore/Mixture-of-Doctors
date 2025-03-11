from .doctors import DiseaseQuestions, get_diseases
from enum import Enum
from pydantic import BaseModel, ValidationError
from kafka import KafkaProducer
from dotenv import load_dotenv
from ollama import Client
from .utilities import logger, PromptTemplate
import string
import os
import json

load_dotenv()

host = os.getenv("CLUSTER_HOST")
port = (lambda p: int(p) if p else None)(os.getenv("CLUSTER_PORT"))

llm = Client(host=f"http://{host}:{port}")

producer = KafkaProducer(
    bootstrap_servers=os.getenv('KAFKA_BROKER'),
    value_serializer=lambda v: json.dumps(v).encode('utf-8'),
)


def build_prompt(template: str, **kwargs) -> str:
    with open(template, "r") as f:
        content = f.read()
    return string.Template(content).substitute(kwargs)

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
