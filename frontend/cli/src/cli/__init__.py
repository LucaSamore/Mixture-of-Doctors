import os

USERNAME_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "username.txt")


def write_username_to_file(username: str) -> None:
    with open(USERNAME_FILE, "w") as file:
        file.write(username)


def read_username_from_file() -> str | None:
    if not os.path.exists(USERNAME_FILE):
        return None
    with open(USERNAME_FILE, "r") as file:
        return file.read()
