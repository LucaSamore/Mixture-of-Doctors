import typer
from typer import Option

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
    """
    set global variable to username
    save new chat for username (empty doc in db)
    print welcome message
    print help message
    """
    pass


@mod_app.command()
def restore(username: str) -> None:
    """
    set global variable to username
    restore chat for username (from db)
    print chat history
    print help message
    """
    pass


@mod_app.command()
def chat(username: str) -> None:
    """
    set global variable to username
    restore chat for username (from db) or create new chat (empty doc in db)
    print chat history (if present) or welcome message
    print help message
    """
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
        precondition: username variable is not empty
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


if __name__ == "__main__":
    app()
