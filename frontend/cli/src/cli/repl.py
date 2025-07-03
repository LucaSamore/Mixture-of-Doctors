from typing import List, Optional
from cli.client import mod_app
import typer
import sys
import shlex
import re

BANNER = """
╔══════════════════════════════════════════════════╗
║                                                  ║
║            MIXTURE OF DOCTORS (MOD)              ║
║                  REPL Interface                  ║
║                                                  ║
╚══════════════════════════════════════════════════╝

Type 'mod' commands directly (e.g., 'mod --help', 'mod new username')
Type 'help' to see available commands
Type 'quit' or 'exit' to exit the REPL
"""

HELP_TEXT = """
Available commands:
  mod [options]           - Execute a MOD CLI command
  help                    - Show this help message
  quit, exit              - Exit the REPL

Examples:
  mod --help              - Show MOD CLI help
  mod new johndoe         - Create a new chat session for johndoe
  mod chat johndoe        - Start or restore a chat session
  mod ask "How are you?"  - Ask a question to the virtual doctor
  mod quit                - Close the current chat session
"""


class StreamFilter:
    """Filter to handle output streams and avoid unwanted messages."""

    def __init__(self, original_stream):
        self.original_stream = original_stream
        self.line_buffer = ""

    def write(self, text):
        self.line_buffer += text
        lines = self.line_buffer.split("\n")

        if len(lines) > 1:
            for line in lines[:-1]:
                if "Try 'python -m cli" in line:
                    modified_line = re.sub(
                        r"Try 'python -m cli\.[^']*'", "Try 'mod --help'", line
                    )
                    self.original_stream.write(modified_line + "\n")
                else:
                    self.original_stream.write(line + "\n")
            self.line_buffer = lines[-1]

    def flush(self):
        if self.line_buffer:
            if "Try 'python -m cli" in self.line_buffer:
                modified_buffer = re.sub(
                    r"Try 'python -m cli\.[^']*'", "Try 'mod --help'", self.line_buffer
                )
                self.original_stream.write(modified_buffer)
            else:
                self.original_stream.write(self.line_buffer)
        self.line_buffer = ""
        self.original_stream.flush()


def start_repl_mode() -> None:
    """Start the REPL mode for interactive CLI usage."""
    typer.echo(BANNER)

    while True:
        try:
            user_input = input("Mixture-of-Doctors> ")
            command = parse_repl_input(user_input)
            if command:
                execute_cli_command(command)
        except KeyboardInterrupt:
            typer.echo("\nKeyboard interrupt received. To exit, type 'quit' or 'exit'.")
        except EOFError:
            typer.echo("\nExiting MOD CLI REPL...")
            break
        except Exception as e:
            typer.echo(f"Unexpected error: {e}")


def parse_repl_input(user_input: str) -> Optional[List[str]]:
    """Parse user input from the REPL and return command tokens."""
    if not user_input.strip():
        return None

    if user_input.strip().lower() in ["quit", "exit"]:
        typer.echo("Exiting MOD CLI REPL...")
        sys.exit(0)

    if user_input.strip().lower() == "help":
        typer.echo(HELP_TEXT)
        return None

    try:
        return shlex.split(user_input)
    except ValueError as e:
        typer.echo(f"Error parsing input: {e}")
        return None


def execute_cli_command(command_args):
    """Execute a CLI command with the given arguments."""
    original_argv = sys.argv.copy()
    original_stdout = sys.stdout
    original_stderr = sys.stderr

    try:
        sys.stdout = StreamFilter(original_stdout)
        sys.stderr = StreamFilter(original_stderr)
        sys.argv = command_args

        try:
            mod_app()
        except SystemExit:
            pass
    except Exception as e:
        typer.echo(f"Error executing command: {e}")
    finally:
        sys.stdout.flush()
        sys.stderr.flush()
        sys.stdout = original_stdout
        sys.stderr = original_stderr
        sys.argv = original_argv
