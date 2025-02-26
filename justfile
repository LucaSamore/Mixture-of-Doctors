alias s := setup
alias p := pre_commit
alias l := lint
alias f := format

install:
	uv sync --all-packages
	
pre_commit_setup:
	uv run pre-commit install

setup: install pre_commit_setup

pre_commit:
	uv run pre-commit run --all-files
	
lint:
	uv run ruff check
	
format:
	uv run ruff format

cli:
    uv run python frontend/cli/src/cli/client.py