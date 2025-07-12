alias s := setup
alias p := pre_commit
alias l := lint
alias f := format
alias d := deploy
alias u := undeploy

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

deploy:
	./scripts/deploy.sh

undeploy:
	./scripts/undeploy.sh