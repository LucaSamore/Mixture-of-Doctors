import asyncio
from websockets.asyncio.server import serve


async def hello(websocket):
    msg = await websocket.recv()
    print(f"FROM Client: {msg}")
    await websocket.send("Hello from server!")


async def main():
    async with serve(hello, "localhost", 8765) as server:
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
