from websockets.sync.client import connect


def hello():
    uri = "ws://localhost:8765"
    with connect(uri) as websocket:
        websocket.send("Hello from client!")
        msg = websocket.recv()
        print(f"FROM Server: {msg}")


if __name__ == "__main__":
    hello()
