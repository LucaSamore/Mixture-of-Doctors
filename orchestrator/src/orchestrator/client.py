import os
from websockets.sync.client import connect
from dotenv import load_dotenv

load_dotenv()

host = os.getenv("WEBSOCKET_SERVER_HOST")
port = (lambda p: int(p) if p else None)(os.getenv("WEBSOCKET_SERVER_PORT"))


def main():
    uri = f"ws://{host}:{port}"
    with connect(uri) as websocket:
        for i in range(5):
            print(f"{i + 1}: Hello from client!")
            websocket.send(f"{i + 1}: Hello from client!")
            msg = websocket.recv()
            print(f"FROM Server: {msg}")


if __name__ == "__main__":
    main()
