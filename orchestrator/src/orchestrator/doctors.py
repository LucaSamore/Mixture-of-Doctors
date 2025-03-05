from pydantic import BaseModel
from typing import List

# Kafka configuration here...


class DiseaseQuestion(BaseModel):
    disease: str
    question: str


type DiseaseQuestions = List[DiseaseQuestion]


def ask_doctor(query: DiseaseQuestion) -> None:
    # publish query.question to query.disease kafka topic
    pass


def get_diseases() -> List[str]:
    # hard-coded for now
    # configuration file later...
    return ["diabetes", "multiple sclerosis", "hypertension"]
