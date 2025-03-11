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

redis:
	docker-compose --env-file ./infrastructure/.env -f ./infrastructure/redis/docker-compose.yml up