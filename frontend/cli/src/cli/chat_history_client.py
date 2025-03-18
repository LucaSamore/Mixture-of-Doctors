import os
import requests
from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime
from dotenv import load_dotenv
from typing import Callable

load_dotenv()


class ConversationItem(BaseModel):
    question: str
    answer: str
    timestamp: datetime = datetime.now()


class ConversationModel(BaseModel):
    username: str
    created_at: datetime
    conversation: List[ConversationItem]


class ChatHistoryClient:
    def __init__(self):
        # Get the base URL from environment variable or use default
        self.base_url = os.getenv("CHAT_HISTORY_API_URL", "http://localhost:8000")

    def create_chat(self, username: str, print_fn: Callable):
        try:
            response = requests.post(
                f"{self.base_url}/requests/", params={"username": username}
            )

            if response.status_code != 200:
                print_fn(
                    f"Failed to create chat: {response.status_code} - {response.text}"
                )
                return

        except Exception as e:
            print_fn(f"Error communicating with chat history service: {e}")

    def create_or_update_chat(
        self, username: str, question: str, answer: str, print_fn: Callable
    ) -> Optional[ConversationModel]:
        try:
            conversation_item = ConversationItem(question=question, answer=answer)

            response = requests.post(
                f"{self.base_url}/requests/",
                params={"username": username},
                json=conversation_item.model_dump(mode="json"),
            )

            if response.status_code == 200:
                return ConversationModel.model_validate(response.json())
            else:
                print_fn(
                    f"Failed to create/update chat: {response.status_code} - {response.text}"
                )
                return None

        except Exception as e:
            print_fn(f"Error communicating with chat history service: {e}")
            return None

    def get_chat_history(
        self, username: str, print_fn: Callable
    ) -> Optional[ConversationModel]:
        try:
            response = requests.get(f"{self.base_url}/requests/{username}")

            if response.status_code == 200:
                return ConversationModel.model_validate(response.json())
            elif response.status_code == 404:
                return None
            else:
                print_fn(
                    f"Failed to get chat history: {response.status_code} - {response.text}"
                )
                return None

        except Exception as e:
            print_fn(f"Error communicating with chat history service: {e}")
            return None

    def delete_chat_history(self, username: str, print_fn: Callable) -> bool:
        try:
            response = requests.delete(f"{self.base_url}/requests/{username}")

            if response.status_code == 204:
                return True
            else:
                print_fn(
                    f"Failed to delete chat history: {response.status_code} - {response.text}"
                )
                return False

        except Exception as e:
            print_fn(f"Error communicating with chat history service: {e}")
            return False
