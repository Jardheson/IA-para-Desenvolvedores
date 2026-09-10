# Variáveis
PYTHON ?= python
PIP ?= pip
UVICORN ?= uvicorn
MODULE ?= src.api.app:app
HOST ?= 127.0.0.1
PORT ?= 8000

# --- Alvos ---

.PHONY: install dev test lint ci help

help:
	@echo "install   Instala dependências de projeto + dev"
	@echo "dev       Sobe API FastAPI em modo reload"
	@echo "test      Executa pytest com cobertura mínima"
	@echo "lint      Roda ruff sobre src e tests"
	@echo "ci        Pipeline local: lint -> test -> build-validate"

install:
	$(PIP) install -e ".[dev]"

dev:
	$(UVICORN) $(MODULE) --host $(HOST) --port $(PORT) --reload

test:
	$(PYTHON) -m pytest --cov=src --cov-report=term --cov-report=xml:coverage.xml --cov-report=html:htmlcov

lint:
	$(PYTHON) -m ruff check .

build-validate:
	$(PYTHON) -m compileall -q src tests
	$(PYTHON) -c "from src.config import settings; print('smoke ok:', type(settings).__name__)"

ci: lint test build-validate
