import typer
from typer import Option
from cli.stream_client import StreamClient
from cli import write_username_to_file, read_username_from_file
from cli.chat_history_client import ChatHistoryClient
import os

app = typer.Typer()
chat_history_client = ChatHistoryClient()
stream_client = StreamClient()


@app.command()
def mod() -> None:
    """
    Mixture of Doctors (MOD) CLI client.

    This tool allows you to interact with the virtual doctor system for self-management of chronic diseases.

    Available subcommands:
    - new: Create a new chat session
    - restore: Continue an existing chat session
    - chat: Start or restore a chat session
    - ask: Ask a question to the virtual doctor
    - quit: Close the current chat session
    """
    typer.echo("Welcome to Mixture of Doctors!")
    typer.echo("Use 'mod --help' to see available commands.")


mod_app = typer.Typer()
app.add_typer(mod_app, name="mod")


@mod_app.command()
def new(username: str) -> None:
    """
    Create a new chat with the virtual doctor.
    """
    new_chat(username)


@mod_app.command()
def restore(username: str) -> None:
    """
    Continue an existing chat with the virtual doctor.
    """
    restore_chat(username)


@mod_app.command()
def chat(username: str) -> None:
    """
    Start a chat with the virtual doctor.
    """
    username_from_file = read_username_from_file()
    if username_from_file is None:
        new_chat(username)
    else:
        restore_chat(username_from_file)


@mod_app.command()
def ask(
    question: str,
    oneshot: bool = Option(
        False, "--oneshot", is_flag=True, help="Ask without saving to chat history"
    ),
) -> None:
    """
    Ask question to virtual doctor.
    """
    # Use local variables instead of globals
    current_answer = None

    username_from_file = read_username_from_file()
    if username_from_file is None:
        typer.echo(
            "Before asking a question, it is necessary to start the chat and authenticate. Launch the command 'chat' or 'restore' or 'new'"
        )
        return

    if not oneshot and question:
        display_chat_history(username_from_file)

    # Custom callback to print and capture the answer
    def capture_answer(message, message_type=None, end="\n"):
        nonlocal current_answer  # Use nonlocal instead of global
        typer.echo(message, nl=(end == "\n"))
        if message_type is None:
            if current_answer is None:
                current_answer = message
            else:
                current_answer += message

    typer.echo(f"\n{username_from_file.title()}: {question}")
    typer.echo("Virtual Doctor: ", nl=False)

    stream_client.send_request(question, username_from_file, capture_answer)

    if not oneshot and question and current_answer:
        chat_history_client.create_or_update_chat(
            username_from_file, question, current_answer
        )


@mod_app.command()
def quit() -> None:
    """
    Close current chat with virtual doctor.
    """
    # Remove the username file to end session
    if os.path.exists(os.path.dirname(os.path.abspath(__file__)) + "/username.txt"):
        os.remove(os.path.dirname(os.path.abspath(__file__)) + "/username.txt")
    typer.echo("Goodbye!")


def new_chat(username: str):
    write_username_to_file(username)

    welcome_message = "I'm your virtual doctor, ready to assist with your health questions. How can I help you today?"

    chat_history_client.create_or_update_chat(
        username,
        "Create a chat session",
        welcome_message,
    )

    typer.echo(f"Welcome, {username}! A new chat session has been created for you.")
    typer.echo(welcome_message)
    print_help_message()


def restore_chat(username: str):
    write_username_to_file(username)
    display_chat_history(username)
    print_help_message()


def display_chat_history(username: str):
    history = chat_history_client.get_chat_history(username)

    if history and history.conversation:
        typer.echo("\n=== Chat History ===")
        for i, item in enumerate(history.conversation):
            typer.echo(f"\n{username.title()}: {item.question}")
            typer.echo(f"Virtual Doctor: {item.answer}")
    else:
        typer.echo("No chat history found or unable to retrieve chat history.")


def print_help_message():
    """Print help information for the user."""
    typer.echo("\nAvailable commands:")
    typer.echo('  - ask "your question"    : Ask a question to the virtual doctor')
    typer.echo("  - quit                   : End the current chat session")
    typer.echo("\nFor more options, type 'mod --help'")


if __name__ == "__main__":
    app()
