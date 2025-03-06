from websockets.asyncio.server import serve
from websockets.exceptions import ConnectionClosed
from dotenv import load_dotenv
from .planning import reason, act
from .utilities import logger
import os

load_dotenv()

host = os.getenv("WEBSOCKET_SERVER_HOST")
port = (lambda p: int(p) if p else None)(os.getenv("WEBSOCKET_SERVER_PORT"))


async def handle_incoming_query(websocket):
    try:
        async for message in websocket:
            logger.info(f"Received query: {message}")
            outcome = reason(message)
            if outcome is not None:
                act(outcome, message)
            else:
                error = "An error occurred while reasoning"
                await websocket.send(error)
                logger.error(error)
            await websocket.send("Hello from server!")
            logger.info("Response sent")
    except ConnectionClosed:
        logger.error("Connection closed by client")


async def server():
    async with serve(handler=handle_incoming_query, host=host, port=port) as server:
        logger.info(f"Server started at ws://{host}:{port}")
        await server.serve_forever()
