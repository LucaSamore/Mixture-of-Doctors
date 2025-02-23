import typer
from typer import Option
from cli import write_username_to_file, read_username_from_file

app = typer.Typer()


@app.command()
def mod() -> None:
    """
    short description of mod command, a welcome message and list of subcommands
    """
    pass


mod_app = typer.Typer()
app.add_typer(mod_app, name="mod")


@mod_app.command()
def new(username: str) -> None:
    new_chat(username)


@mod_app.command()
def restore(username: str) -> None:
    restore_chat(username)


@mod_app.command()
def chat(username: str) -> None:
    username_from_file = read_username_from_file()
    if username_from_file is None:
        new_chat(username)
    else:
        restore_chat(username_from_file)
    pass


@mod_app.command()
def ask(
    question: str, oneshot: bool = Option(False, "--oneshot", is_flag=True, help="")
) -> None:
    if oneshot:
        """
        ask question to chatbot
        retrieve answer
        print answer
        """
        print("Oneshot")
    else:
        """
        precondition: username retrieved from file is not empty
                      if empty, print error message and return
        ask question to chatbot
        retrieve answer
        save question and answer in chat history (db)
        print chat history
        print answer
        """
        print("Non-oneshot")


@mod_app.command()
def quit() -> None:
    """
    print goodbye message
    """
    print("Goodbye!")


def new_chat(username: str):
    write_username_to_file(username)
    print("New chat:" + username)
    """
    save new chat for username (empty doc in db)
    print welcome message
    print help message
    """


def restore_chat(username: str):
    write_username_to_file(username)
    print("Restore")
    """
    restore chat for username (from db)
    print chat history
    print help message
    """


if __name__ == "__main__":
    app()
