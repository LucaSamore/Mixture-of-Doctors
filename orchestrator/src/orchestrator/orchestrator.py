import asyncio
import os
from websockets.asyncio.server import serve
from websockets.exceptions import ConnectionClosedOK
from dotenv import load_dotenv

load_dotenv()

host = os.getenv("WEBSOCKET_SERVER_HOST")
port = (lambda p: int(p) if p else None)(os.getenv("WEBSOCKET_SERVER_PORT"))


async def handle_incoming_query(websocket):
    try:
        async for message in websocket:
            print(f"FROM Client: {message}")
            await websocket.send("Hello from server!")
    except ConnectionClosedOK:
        print("Connection closed by client")


async def main():
    async with serve(handler=handle_incoming_query, host=host, port=port) as server:
        await server.serve_forever()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nServer stopped")
