from pydantic import BaseModel, Field
from datetime import datetime
from typing import List


class ConversationItem(BaseModel):
    """
    Model for a single conversation item
    """

    question: str = Field(..., description="Question sent by the user", min_length=1)
    answer: str = Field(..., description="Answer provided to the user", min_length=1)
    timestamp: datetime = Field(
        default_factory=datetime.now,
        description="Date and time of the conversation item",
    )


class ConversationModel(BaseModel):
    """
    Model for a user's conversation
    """

    username: str = Field(..., description="Unique username for the user")
    created_at: datetime = Field(
        default_factory=datetime.now, description="Date and time when "
    )
    conversation: List[ConversationItem] = Field(
        default_factory=list, description="List of conversation items"
    )

    class Config:
        schema_extra = {
            "example": {
                "username": "Roberto",
                "created_at": datetime.now().isoformat(),
                "conversation": [
                    {
                        "question": "How does this API work?",
                        "answer": "This API works like this...",
                        "timestamp": datetime.now().isoformat(),
                    },
                    {
                        "question": "What are the benefits?",
                        "answer": "The benefits are...",
                        "timestamp": datetime.now().isoformat(),
                    },
                ],
            }
        }
