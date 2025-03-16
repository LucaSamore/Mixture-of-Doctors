from pydantic import BaseModel, Field
from datetime import datetime
from typing import List


class ConversationItem(BaseModel):
    question: str = Field(..., description="Question of user", min_length=1)
    answer: str = Field(..., description="Answering ... ", min_length=1)
    timestamp: datetime = Field(default_factory=datetime.now)


class ConversationModel(BaseModel):
    username: str = Field(..., description="Username of the user")
    created_at: datetime = Field(default_factory=datetime.now)
    conversation: List[ConversationItem] = Field(default_factory=list)

    model_config = {
        "json_schema_extra": {
            "example": {
                "username": "Roberto",
                "created_at": datetime.now().isoformat(),
                "conversation": [
                    {
                        "question": "How does the API work?",
                        "answer": "The API is a RESTful API that allows you to store and retrieve chat history data.",
                        "timestamp": datetime.now().isoformat(),
                    }
                ]
            }
        }
    }