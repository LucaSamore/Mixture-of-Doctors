import requests
from redis import Redis, RedisError
import time
import os
import random
from typing import Any, Callable
from pydantic import BaseModel
from loguru import logger
from dotenv import load_dotenv

load_dotenv()

type Query = str


class Response(BaseModel):
    query: str
    response: str
    done: str


class StreamClient:
    def __init__(self):
        # Initialize instance variables from environment
        self.last_message_processed_id = None
        self.request_timeout = int(os.getenv("REQUEST_TIMEOUT", "30"))
        self.orchestrator_url = os.getenv(
            "ORCHESTRATOR_URL", "http://your-nginx-url/path"
        )
        self.redis_host = os.getenv("REDIS_HOST", "localhost")
        self.redis_port = int(os.getenv("REDIS_PORT", "6379"))
        self.redis_password = os.getenv("REDIS_PASSWORD", None)

        # Flag to indicate whether to add new line after printing responses
        self.print_newline = False

        # Create logs directory
        log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "logs")
        os.makedirs(log_dir, exist_ok=True)

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

    def create_redis_connection(self) -> Redis | None:
        try:
            redis_client = Redis(
                host=self.redis_host,
                port=self.redis_port,
                password=self.redis_password if self.redis_password else None,
                decode_responses=True,
            )
            redis_client.ping()
            return redis_client
        except ConnectionError as e:
            logger.error(f"Failed to connect to Redis: {e}")
            return None

    def send_request(self, query: Query, user_id: str, print_fn: Callable) -> None:
        payload = {"query": query, "user_id": user_id, "plain_text": True}

        # Get the last message ID before sending the request
        self._update_last_message_id(user_id)

        try:
            logger.info(f"Sending request to {self.orchestrator_url}")
            response = requests.post(
                self.orchestrator_url, json=payload, timeout=self.request_timeout
            )

            match response.status_code:
                case 204:
                    logger.info("Request accepted, reading from stream...")
                    self.read_from_stream(user_id, print_fn)
                case 500:
                    logger.error(
                        f"Server error: {response.status_code} - {response.text}"
                    )
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

    def _update_last_message_id(self, user_id: str) -> None:
        redis_client = self.create_redis_connection()
        if redis_client:
            latest_messages = redis_client.xrevrange(user_id, count=1)

            if latest_messages:
                self.last_message_processed_id = latest_messages[0][0]  # type: ignore
                logger.debug(
                    f"Last message ID before request: {self.last_message_processed_id}"
                )
            else:
                self.last_message_processed_id = "0"
                logger.debug("No previous messages found, starting from 0")

    def read_from_stream(self, user_id: str, print_fn: Callable) -> None:
        redis_client = self.create_redis_connection()
        if redis_client is None:
            return
        logger.debug(f"Reading from stream key: {user_id}")

        read_id = self.starting_point(user_id, redis_client)
        logger.debug(f"Starting from message ID: {read_id}")
        try:
            while True:
                response = redis_client.xread({user_id: read_id}, count=10, block=2000)

                logger.debug(f"Response type: {type(response)}, Value: {response}")

                if not response:
                    logger.debug("No messages received, waiting...")
                    time.sleep(1)
                    continue

                # Check if we need to stop processing messages
                should_stop = self.process_redis_response(response, print_fn)
                if should_stop:
                    logger.info("Received stop signal. Exiting stream processing.")
                    break

                # Get the latest message ID we just processed
                if self.last_message_processed_id:
                    read_id = (
                        self.last_message_processed_id
                    )  # Start from last processed message

        except RedisError as e:
            logger.error(f"Redis error: {e}")
            print_fn(f"Error connecting to message stream: {str(e)}", "error")

        except Exception as e:
            logger.exception("Unexpected error")
            print_fn(f"Unexpected error: {str(e)}", "error")

    def starting_point(self, user_id: str, redis_client: Redis) -> str:
        if not self.last_message_processed_id:
            return "0"

        next_messages = redis_client.xrange(
            user_id,
            min=f"({self.last_message_processed_id}",
            max="+",  # Until the end of the stream
        )

        if next_messages:
            read_id = next_messages[0][0]  # type: ignore
            logger.debug(f"Found new messages, starting from ID: {read_id}")
            return read_id

        logger.debug("No new messages yet, waiting with ID: $")
        return "$"

    def process_redis_response(self, response: Any, print_fn: Callable) -> bool:
        try:
            logger.debug(f"Processing Redis response: {response}")
            should_stop = False

            # Validate a list...
            self.format_is_valid(
                isinstance(response, list), response, "response", print_fn
            )

            for stream_entry in response:
                # ... of list ... (lenght 2: key of type str - USER - and value of type list - STREAM -)
                self.format_is_valid(
                    (isinstance(stream_entry, list) and len(stream_entry) == 2),
                    stream_entry,
                    "stream_entry",
                    print_fn,
                )

                _, messages = stream_entry

                # ... of list (1 element per stream chunk)...
                self.format_is_valid(
                    isinstance(messages, list), messages, "messages", print_fn
                )

                # ... of tuple (single stream chunk)
                for message in messages:
                    self.format_is_valid(
                        (isinstance(message, tuple) and len(message) == 2),
                        message,
                        "message",
                        print_fn,
                    )

                    message_id, data = message
                    self.last_message_processed_id = message_id
                    if self.process_message(message_id, data, print_fn):
                        should_stop = True

            return should_stop

        except ValueError as e:
            logger.exception(f"Format validation error: {e}")
            print_fn(f"Error processing message: {str(e)}", "error")
            raise
        except Exception as e:
            logger.exception(f"Error processing Redis response: {e}")
            print_fn(f"Error processing message: {str(e)}", "error")
            return False

    def format_is_valid(
        self,
        condition: bool,
        checked_object: Any,
        checked_name: str,
        print_fn: Callable,
    ) -> None:
        if not condition:
            logger.error(
                f"Unexpected Redis {checked_name} format: {type(checked_object)}"
            )
            raise ValueError(f"Invalid {checked_name} format")

    def process_message(self, message_id: str, data: Any, print_fn: Callable) -> bool:
        logger.debug(f"Processing message with ID: {message_id}")
        logger.debug(f"Message data: {data}")
        logger.info(f"Message received: {message_id}")

        try:
            # Handle case where data is already a dictionary (not a JSON string)
            if isinstance(data, dict):
                response_obj = Response.model_validate(data)
            else:
                response_obj = Response.model_validate_json(data)

            logger.debug(f"Parsed response object: {response_obj}")

            # Check if this is the stop message
            if response_obj.done == "stop":
                print_fn("\n", end="")
                logger.debug("Received 'stop' signal, will exit stream processing")
                return True  # Signal to stop processing

            # Add a small random delay to simulate typing (between 5-20 milliseconds)
            time.sleep(random.uniform(0.005, 0.02))

            # Print the response without newline
            print_fn(response_obj.response, end="")
            return False  # Continue processing messages

        except Exception as e:
            logger.error(f"Failed to parse response model: {e}")
            print_fn(f"\nMessage: {data}", "error")
            return False  # Continue processing in case of error
