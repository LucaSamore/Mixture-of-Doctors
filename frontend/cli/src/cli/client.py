import typer
from typer import Option
from cli.stream_client import send_request
from cli import write_username_to_file, read_username_from_file

app = typer.Typer()


@app.command()
def mod() -> None:
    """
    TODO: short description of mod command, a welcome message and list of subcommands
    """
    pass


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
    question: str, oneshot: bool = Option(False, "--oneshot", is_flag=True, help="")
) -> None:
    """
    Ask question to virtual doctor.
    """
    username_from_file = read_username_from_file()
    if username_from_file is None:
        typer.echo(
            "Before asking a question, it is necessary to start the chat and authenticate. Launch the command 'chat' or 'restore' or 'new'"
        )
    else:
        send_request(question, username_from_file, typer.echo)
    if not oneshot:
        # save question and answer in chat history (db)
        # print chat history
        pass


@mod_app.command()
def quit() -> None:
    """
    Close current chat with virtual doctor.
    """
    print("Goodbye!")


def new_chat(username: str):
    write_username_to_file(username)
    """
    save new chat for username (empty doc in db)
    print welcome message
    print help message
    """


def restore_chat(username: str):
    write_username_to_file(username)
    """
    restore chat for username (from db)
    print chat history
    print help message
    """


if __name__ == "__main__":
    app()
