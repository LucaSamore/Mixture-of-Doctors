import json
import websockets
from pydantic import BaseModel, ValidationError
from typing import AsyncGenerator, Optional, List
from dataclasses import dataclass

WEBSOCKET_SERVER = "ws://localhost:8000/ws"

type User = str
type Query = str


@dataclass
class Error:
    reason: str


class Response(BaseModel):
    model: str
    created_at: str
    response: str
    done: bool
    done_reason: Optional[str] = None
    context: Optional[List[int]] = None  # Fixed default value


class Request(BaseModel):
    sender: User
    message: Query


async def connect(username, query) -> AsyncGenerator[Response, None]:
    try:
        print(f"Connecting to WebSocket at {WEBSOCKET_SERVER}")
        async with websockets.connect(WEBSOCKET_SERVER) as websocket:
            print("Connection established")
            request = build_request(username, query)
            await websocket.send(
                request.model_dump_json()
            )  # Ensure JSON is properly formatted
            print("Message sent")

            async for message in websocket:
                try:
                    payload = json.loads(message)  # Decode received JSON
                    response = Response.model_validate(
                        payload
                    )  # Validate and parse with Pydantic
                    yield response  # Yield valid response
                except (json.JSONDecodeError, ValidationError) as e:
                    print(f"Error parsing message: {e}")
                    continue  # Skip invalid messages
    except Exception as e:
        print(f"WebSocket connection error: {e}")


async def print_response(username, query, print_fn):
    async for response in connect(username, query):
        if isinstance(response, Error):
            print_fn(f"Error: {response.reason}")
        else:
            print_fn(response.response)


def build_request(username, query) -> Request:
    return Request(sender=username, message=query)
