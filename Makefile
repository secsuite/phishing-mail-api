PYTHON_BIN ?= python3.12
VENV ?= .venv
PYTHON := $(VENV)/bin/python
BLACK := $(VENV)/bin/black
RUFF := $(VENV)/bin/ruff
MYPY := $(VENV)/bin/mypy
PYTEST := $(VENV)/bin/pytest
PRE_COMMIT := $(VENV)/bin/pre-commit
PYTEST_WORKERS ?= 1
TORCH_INDEX_URL ?= https://download.pytorch.org/whl/cpu

.PHONY: install-runtime install-dev install-train quality quality-fix test-fast test-integration precommit

install-runtime:
	command -v $(PYTHON_BIN) >/dev/null 2>&1 || (echo "Missing $(PYTHON_BIN). Install Python 3.12 or run 'make install-runtime PYTHON_BIN=python3'." && exit 1)
	chmod -R u+w $(VENV) 2>/dev/null || true
	rm -rf $(VENV)
	$(PYTHON_BIN) -m venv $(VENV)
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -r requirements.txt
	$(PYTHON) -m pip install black ruff mypy pytest pytest-xdist pre-commit httpx
	$(PRE_COMMIT) install --hook-type pre-commit --hook-type pre-push
	$(PRE_COMMIT) install-hooks

install-dev: install-runtime

install-train:
	@test -x "$(PYTHON)" || (echo "Missing $(PYTHON). Run 'make install-runtime' first." && exit 1)
	$(PYTHON) -m pip install --index-url $(TORCH_INDEX_URL) --extra-index-url https://pypi.org/simple torch
	$(PYTHON) -m pip install --extra-index-url $(TORCH_INDEX_URL) -r requirements-train.txt

quality:
	$(BLACK) --check app tests
	$(RUFF) check app tests
	$(MYPY) app tests
	$(MAKE) test-fast

quality-fix:
	$(BLACK) app tests
	$(RUFF) check app tests --fix
	$(MYPY) app tests
	$(MAKE) test-fast

test-fast:
	$(PYTEST) -q --maxfail=1 $(if $(filter 1,$(PYTEST_WORKERS)),,-n $(PYTEST_WORKERS)) -m "not integration"

test-integration:
	$(PYTEST) -q --maxfail=1 -m "integration"

precommit:
	$(PRE_COMMIT) run --all-files
