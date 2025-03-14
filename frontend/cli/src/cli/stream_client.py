import requests
from redis import Redis, RedisError
import time
import os
from typing import Any, Callable
from pydantic import BaseModel
from loguru import logger

type Query = str

LAST_MESSAGE_PROCESSED_ID = ""
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "30"))
ORCHESTRATOR_URL = os.getenv("ORCHESTRATOR_URL", "http://your-nginx-url/path")

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", None)


class Response(BaseModel):
    query: str
    response: str
    done: str


log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "logs")

# Configure logger
logger.remove()
logger.add(
    os.path.join(log_dir, "stream_client_{time}.log"),
    rotation="10 MB",
    level="DEBUG",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
    backtrace=True,
    diagnose=True,
)


def create_redis_connection() -> Redis | None:
    try:
        redis_client = Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            password=REDIS_PASSWORD if REDIS_PASSWORD else None,
            decode_responses=True,
        )
        redis_client.ping()
        return redis_client
    except ConnectionError as e:
        logger.error(f"Failed to connect to Redis: {e}")
        return None


def send_request(query: Query, user_id: str, print_fn) -> None:
    global LAST_MESSAGE_PROCESSED_ID

    payload = {"query": query, "user_id": user_id}

    try:
        logger.info(f"Sending request to {ORCHESTRATOR_URL}")
        response = requests.post(
            ORCHESTRATOR_URL, json=payload, timeout=REQUEST_TIMEOUT
        )

        match response.status_code:
            case 204:
                logger.info("Request accepted, reading from stream...")
                print_fn("Request accepted, waiting for response...")
                read_from_stream(user_id, print_fn)
            case 500:
                logger.error(f"Server error: {response.status_code} - {response.text}")
                print_fn(
                    f"The server encountered a problem. Status code: {response.status_code}",
                    "error",
                )
            case _:
                logger.warning(
                    f"Unexpected status code: {response.status_code} - {response.text}"
                )
                print_fn(
                    f"Unexpected response (status {response.status_code})",
                    "warning",
                )

    except requests.Timeout:
        logger.error("Request timed out")
        print_fn("Request timed out. Please try again later.", "error")

    except requests.RequestException as e:
        logger.error(f"Request failed: {e}")
        print_fn(f"Failed to send request: {str(e)}", "error")


def read_from_stream(user_id: str, print_fn: Callable) -> None:
    global LAST_MESSAGE_PROCESSED_ID

    redis_client = create_redis_connection()
    if redis_client is None:
        return
    logger.debug(f"Reading from stream key: {user_id}")

    read_id = starting_point()
    logger.debug(f"Starting from message ID: {read_id}")

    try:
        while True:
            response = redis_client.xread({user_id: read_id}, count=10, block=2000)

            logger.debug(f"Response type: {type(response)}, Value: {response}")

            if not response:
                logger.debug("No messages received, waiting...")
                time.sleep(1)
                read_id = ">"  # Read incoming message from now
                continue

            process_redis_response(response, print_fn)
            read_id = ">"  # Read incoming message from now

    except RedisError as e:
        logger.error(f"Redis error: {e}")
        print_fn(f"Error connecting to message stream: {str(e)}", "error")

    except Exception as e:
        logger.exception("Unexpected error")
        print_fn(f"Unexpected error: {str(e)}", "error")


def starting_point() -> str:
    return "0" if LAST_MESSAGE_PROCESSED_ID == "" else LAST_MESSAGE_PROCESSED_ID


def process_redis_response(response: Any, print_fn: Callable) -> None:
    global LAST_MESSAGE_PROCESSED_ID

    try:
        logger.debug(f"Processing Redis response: {response}")

        format_is_valid(isinstance(response, list), response, "response", print_fn)

        for stream_entry in response:
            format_is_valid(
                (isinstance(stream_entry, list) and len(stream_entry) == 2),
                stream_entry,
                "stream_entry",
                print_fn,
            )

            _, messages = stream_entry

            format_is_valid(isinstance(messages, list), messages, "messages", print_fn)

            for message in messages:
                format_is_valid(
                    (isinstance(message, list) and len(message) == 2),
                    message,
                    "message",
                    print_fn,
                )

                message_id, data = message
                LAST_MESSAGE_PROCESSED_ID = message_id
                process_message(message_id, data, print_fn)

    except Exception as e:
        logger.exception(f"Error processing Redis response: {e}")
        print_fn(f"Error processing message: {str(e)}", "error")


def format_is_valid(
    condition: bool, checked_object: Any, checked_name: str, print_fn: Callable
) -> None:
    if not condition:
        logger.error(f"Unexpected Redis {checked_name} format: {type(checked_object)}")
        print_fn("Received message in unknown format", "error")
        raise Exception("Invalid format")


def process_message(message_id: str, data: str, print_fn: Callable) -> None:
    logger.debug(f"Processing message with ID: {message_id}")
    logger.debug(f"Message data: {data}")
    logger.info(f"Message received: {message_id}")

    try:
        response_obj = Response.model_validate_json(data)
        print_fn(response_obj.response)

    except Exception as e:
        logger.error(f"Failed to parse response model: {e}")
        print_fn(f"\nMessage: {data}", "error")
