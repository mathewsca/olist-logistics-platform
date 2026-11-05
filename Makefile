# Atalhos do projeto. Rode `make help` para ver a lista.
# Recipes avoid shell-specific syntax so they work in cmd.exe, Git Bash and Linux (CI).

PYTHON ?= python
VENV   := .venv

ifeq ($(OS),Windows_NT)
	BIN := $(VENV)/Scripts
else
	BIN := $(VENV)/bin
endif

PY := $(BIN)/python

.DEFAULT_GOAL := help
.PHONY: help install setup lint format test coverage test-integration pre-commit \
	up down ingest ingest-dag dbt-build dbt-docs analyses extract dashboard dashboard-docker \
	train export-model release-bundle api api-docker monitor monitor-dag

help: ## Lista os alvos disponiveis
	@$(PYTHON) -c "import re; [print(f'  {m[0]:<18} {m[1]}') for m in re.findall(r'^([a-z-]+):.*?## (.*)$$', open('Makefile', encoding='utf-8').read(), re.M)]"

$(VENV)/pyvenv.cfg:
	$(PYTHON) -m venv $(VENV)

install: $(VENV)/pyvenv.cfg ## Cria o .venv e instala o pacote com dependencias de dev, ingestao, dbt, dashboard, ml, api e monitoring
	$(PY) -m pip install --upgrade pip
	$(PY) -m pip install -e ".[ingestion,dbt,dashboard,ml,api,monitoring,dev]"

setup: install ## install + hooks do pre-commit
	$(BIN)/pre-commit install

lint: ## ruff check + ruff format --check
	$(BIN)/ruff check .
	$(BIN)/ruff format --check .

format: ## Corrige lint e formata o codigo
	$(BIN)/ruff check --fix .
	$(BIN)/ruff format .

test: ## Testes unitarios (exclui integration)
	$(PY) -m pytest

coverage: ## Testes unitarios com relatorio de cobertura (usado no CI)
	$(PY) -m pytest --cov --cov-report=term-missing:skip-covered --cov-report=xml

test-integration: ## Testes de integracao (exige `make up`)
	$(PY) -m pytest -m integration

ingest-dag: ## Dispara a DAG olist_ingestion (ingestao + dbt) no Airflow
	docker compose exec airflow-scheduler airflow dags trigger olist_ingestion

pre-commit: ## Roda todos os hooks em todos os arquivos
	$(BIN)/pre-commit run --all-files

up: ## Sobe Postgres + Airflow (UI em http://localhost:8080) + MLflow (http://localhost:5000)
	docker compose up -d --build

down: ## Derruba os servicos (mantem o volume do banco)
	docker compose --profile dashboard --profile api down

ingest: ## Download do Kaggle + carga na camada raw + checagens (exige `make up`)
	$(PY) -m olist_platform.ingestion run

dbt-build: ## dbt build: modelos + testes (exige `make up` e `make ingest`)
	$(PY) -m olist_platform.transform build

dbt-docs: ## Gera a documentacao do dbt e abre em http://localhost:8081
	$(PY) -m olist_platform.transform docs generate
	$(PY) -m olist_platform.transform docs serve --port 8081

analyses: ## Roda as consultas de dbt/analyses e grava docs/analises.md (exige `make dbt-build`)
	$(PY) -m olist_platform.analytics report

extract: ## Exporta os datasets do dashboard para data/extract/*.parquet (exige `make dbt-build`)
	$(PY) -m olist_platform.analytics extract

dashboard: ## Sobe o dashboard Streamlit em http://localhost:8501 (exige `make dbt-build`)
	$(PY) -m streamlit run dashboard/app.py --browser.gatherUsageStats=false

dashboard-docker: ## Sobe o dashboard no docker compose (perfil dashboard), na mesma porta
	docker compose --profile dashboard up -d --build dashboard

train: ## Treina, compara com os baselines, registra no MLflow e grava docs/modelagem.md (exige `make dbt-build`)
	$(PY) -m olist_platform.models train

export-model: ## Copia os campeoes do MLflow e o lookup de CEPs para models_export/ (exige `make train`)
	$(PY) -m olist_platform.api export

api: ## Sobe a API em http://localhost:8000/docs (MLflow se no ar, senao models_export/)
	$(PY) -m olist_platform.api serve

release-bundle: export-model ## Empacota models_export/ em dist/models_export.tar.gz, o anexo da Release que o release.yml usa
	$(PY) -c "import shutil; print(shutil.make_archive('dist/models_export', 'gztar', base_dir='models_export'))"

api-docker: export-model ## Constroi a imagem da API e sobe no docker compose (perfil api), na mesma porta
	docker compose --profile api up -d --build api

monitor: ## Simula 2018-04..08 em producao (drift, desempenho, retreino, quality gate) e grava docs/monitoramento.md (exige `make dbt-build`)
	$(PY) -m olist_platform.monitoring simulate

monitor-dag: ## Dispara a DAG olist_monitoring_retrain (a mesma simulacao, passo a passo, no Airflow)
	docker compose exec airflow-scheduler airflow dags trigger olist_monitoring_retrain
