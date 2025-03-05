import os
from websockets.sync.client import connect
from dotenv import load_dotenv

load_dotenv()

host = os.getenv("WEBSOCKET_SERVER_HOST")
port = (lambda p: int(p) if p else None)(os.getenv("WEBSOCKET_SERVER_PORT"))


def main():
    uri = f"ws://{host}:{port}"
    with connect(uri, ping_interval=None) as websocket:
        query = "What is the best treatment for diabetes?"
        websocket.send(query)
        message = websocket.recv()
        print(f"FROM Server: {message}")


if __name__ == "__main__":
    main()
