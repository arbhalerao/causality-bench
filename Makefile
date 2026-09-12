BOOTSTRAP_PYTHON ?= python3
VENV := .venv/bin/python
DEPS := .venv/.installed
PYTHON ?= $(VENV)
PIP ?= .venv/bin/pip

EXPERIMENTS := baseline scaling message_rate delay topology failures

.DEFAULT_GOAL := help
.PHONY: help venv install test lint format check experiments analysis figures reproduce clean

help:  ## print this help
	@grep -hE '^[a-z][a-zA-Z0-9_-]*:.*?## ' $(MAKEFILE_LIST) \
		| awk -F':.*?## ' '{printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

$(VENV):
	$(BOOTSTRAP_PYTHON) -m venv .venv
	$(PIP) install --upgrade pip

$(DEPS): $(VENV) pyproject.toml
	$(PIP) install -e ".[dev]"
	@touch $(DEPS)

venv: $(VENV)  ## create .venv if missing

install: $(DEPS)  ## install the package and dev dependencies

test: $(DEPS)  ## run the test suite
	$(PYTHON) -m pytest -v

lint: $(DEPS)  ## check formatting and lint rules
	$(PYTHON) -m ruff check src tests experiments

format: $(DEPS)  ## apply formatting and autofixes
	$(PYTHON) -m black src tests experiments
	$(PYTHON) -m ruff check --fix src tests experiments

check: lint test  ## lint then test

experiments: $(DEPS)  ## run every experiment into results/raw
	@for name in $(EXPERIMENTS); do $(PYTHON) experiments/run_$$name.py; done

analysis: $(DEPS)  ## aggregate raw results into results/processed
	$(PYTHON) experiments/run_analysis.py

figures: $(DEPS)  ## render every figure into results/figures
	$(PYTHON) experiments/make_figures.py

reproduce: experiments analysis figures  ## regenerate every result and figure from scratch

clean:  ## remove the venv, caches, and build artifacts
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
	rm -rf .venv .pytest_cache .ruff_cache build dist src/*.egg-info
