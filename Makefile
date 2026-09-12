BOOTSTRAP_PYTHON ?= python3
VENV := .venv/bin/python
DEPS := .venv/.installed
PYTHON ?= $(VENV)
PIP ?= .venv/bin/pip

.DEFAULT_GOAL := help
.PHONY: help venv install test lint format check clean

help:  ## print this help
	@grep -hE '^[a-z][a-zA-Z0-9_-]*:.*?## ' $(MAKEFILE_LIST) \
		| awk -F':.*?## ' '{printf "  \033[36m%-9s\033[0m %s\n", $$1, $$2}'

$(VENV):
	$(BOOTSTRAP_PYTHON) -m venv .venv
	$(PIP) install --upgrade pip

$(DEPS): $(VENV) pyproject.toml
	$(PIP) install -e ".[dev]"
	@touch $(DEPS)

venv: $(VENV)  ## create .venv if missing

install: $(DEPS)  ## install the package and dev dependencies

test: $(DEPS)  ## run the test suite
	$(PYTHON) -m pytest

lint: $(DEPS)  ## check formatting and lint rules
	$(PYTHON) -m ruff check src tests

format: $(DEPS)  ## apply formatting and autofixes
	$(PYTHON) -m black src tests
	$(PYTHON) -m ruff check --fix src tests

check: lint test  ## lint then test

clean:  ## remove the venv, caches, and build artifacts
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
	rm -rf .venv .pytest_cache .ruff_cache build dist src/*.egg-info
