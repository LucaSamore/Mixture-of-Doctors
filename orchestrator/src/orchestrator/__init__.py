from .websocket_server import server
import asyncio


def main() -> None:
    try:
        asyncio.run(server())
    except KeyboardInterrupt:
        print("\nServer stopped")


if __name__ == "__main__":
    main()
