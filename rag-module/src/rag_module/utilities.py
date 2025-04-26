from pydantic import BaseModel
from datetime import datetime
from dotenv import load_dotenv
from typing import List
import json
import string

load_dotenv()


class ConversationItem(BaseModel):
    question: str
    answer: str
    timestamp: datetime = datetime.now()


class ConversationModel(BaseModel):
    username: str
    created_at: datetime
    conversation: List[ConversationItem]


class DateTimeEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, datetime):
            return o.isoformat()
        return super().default(o)


def prepare_prompt(template: str, **kwargs) -> str:
    with open(template, "r") as f:
        content = f.read()
    return string.Template(content).substitute(kwargs)
