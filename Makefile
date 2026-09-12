BOOTSTRAP_PYTHON ?= python3
VENV := .venv/bin/python
DEPS := .venv/.installed
PYTHON ?= $(VENV)
PIP ?= .venv/bin/pip
JUPYTER ?= .venv/bin/jupyter

EXPERIMENTS := baseline scaling message_rate delay topology failures

.DEFAULT_GOAL := help
.PHONY: help venv install test lint format check experiments analysis figures notebooks generate discard clean

help:  ## print this help
	@grep -hE '^[a-z][a-zA-Z0-9_-]*:.*?## ' $(MAKEFILE_LIST) \
		| awk -F':.*?## ' '{printf "  \033[36m%-13s\033[0m %s\n", $$1, $$2}'

$(VENV):
	$(BOOTSTRAP_PYTHON) -m venv .venv
	$(PIP) install --upgrade pip

$(DEPS): $(VENV) pyproject.toml
	$(PIP) install -e ".[dev,notebook]"
	@touch $(DEPS)

venv: $(VENV)  ## create .venv if missing

install: $(DEPS)  ## install the dependencies

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

notebooks: $(DEPS)  ## re-execute the notebooks against the current results
	$(JUPYTER) nbconvert --execute --inplace --to notebook notebooks/*.ipynb

generate: experiments analysis figures notebooks  ## produce every result, figure, and notebook from scratch

discard:  ## undo generate: delete the results
	rm -rf results/raw results/processed results/figures
	$(JUPYTER) nbconvert --clear-output --inplace notebooks/*.ipynb

clean: discard  ## remove the venv, caches, build artifacts, and generated output
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
	rm -rf .venv .pytest_cache .ruff_cache build dist src/*.egg-info
