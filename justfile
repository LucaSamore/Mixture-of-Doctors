alias s := setup
alias p := pre_commit
alias l := lint
alias f := format
alias o := orchestrator

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

orchestrator:
	uv run python orchestrator/src/orchestrator/orchestrator.py

client:
	uv run python orchestrator/src/orchestrator/client.py

llm:
	uv run python orchestrator/src/orchestrator/planner.py