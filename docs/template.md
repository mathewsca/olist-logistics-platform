# Usar como template

O repositório foi organizado para servir de base a outros projetos de dados *fullstack* do mesmo formato: um
dataset tabular, um problema de previsão no momento de um evento, análise, API e monitoramento. No GitHub, ele
pode ser marcado como *Template repository* (*Settings → General*), e "Use this template" cria uma cópia sem o
histórico.

## O que se reaproveita sem mudar

| Parte | Arquivos |
|---|---|
| Ambiente e qualidade | `pyproject.toml` (extras por componente), `Makefile`, `.pre-commit-config.yaml`, `.gitignore`, `.gitattributes`, `.env.example` |
| Infraestrutura local | `docker-compose.yml`, `docker/postgres/`, `airflow/Dockerfile`, `Dockerfile.api`, `Dockerfile.dashboard` |
| CI/CD | `.github/workflows/` (lint e testes, dbt docs no Pages, release no GHCR), Dependabot, template de PR |
| Carga na camada raw | `ingestion/loader.py`, `ingestion/quality.py`, `ingestion/pipeline.py` (lote atômico, linhagem, checagens) |
| dbt pelo Python | `transform/` (o mesmo caminho para make, DAG e CI) |
| Relatórios rastreáveis | `analytics/report.py` + `dbt/analyses/`, `analytics/quality.py` + seed `data_issues` |
| Treino e registro | `models/train.py`, `models/evaluation.py`, `models/split.py` (MLflow, alias `champion`, limiar pela validação) |
| Serving | `api/bundle.py`, `api/app.py` (MLflow com queda para o pacote exportado) |
| Monitoramento | `monitoring/` (drift com Evidently, gatilhos, *quality gate*, simulação mês a mês) |

## O que é do domínio e precisa ser trocado

1. **Fonte:** `ingestion/sources.py` (arquivos, colunas esperadas) e `ingestion/download.py` se a origem não for
   o Kaggle. Fixtures minúsculas em `tests/fixtures/landing/`.
2. **dbt:** `dbt/models/` (staging, intermediate e o mart no grão do problema), `dbt/tests/business_rules/` e a
   seed `dbt/seeds/data_issues.csv` com as anomalias conhecidas da nova fonte.
3. **Perguntas de negócio:** `dbt/analyses/`, a lista `ANALYSES` em `analytics/report.py` e as métricas
   equivalentes em `analytics/metrics.py` (o teste de integração compara os dois).
4. **Features e alvos:** `features/` (só o que se sabe no momento da previsão), `models/data.py` (consulta de
   treino), `models/baselines.py` e os cortes da divisão temporal em `models/split.py`.
5. **Contrato da API:** `api/schemas.py` e `features/order_input.py`.
6. **Dashboard:** as páginas de `dashboard/views/`.
7. **Janelas do monitoramento:** `monitoring/windows.py`.

## Checklist de renomeação

- Nome do pacote `olist_platform` (pasta em `src/`, imports, `pyproject.toml`, `Makefile`, Dockerfiles, DAGs).
- Nome do projeto dbt e do banco (`olist` em `dbt_project.yml`, `profiles.yml`, compose e `.env.example`).
- Nomes dos modelos no MLflow (`models/train.py`, `monitoring/registry.py`) e das imagens (`olist-api`,
  `olist-dashboard`, `olist-airflow`).
- URL do repositório, do Pages e das imagens no GHCR (README, `docs/deploy.md`, `release.yml`, badges).
- `CHANGELOG.md` zerado e versão `0.1.0` em `src/<pacote>/__init__.py`.

Para achar tudo: `git grep -n -i olist`.

## Ordem sugerida

Ingestão e fixtures → staging e mart com testes → análises e dashboard → features, baselines e treino → API →
monitoramento. Cada etapa fecha com `make lint test` verde e números novos só a partir de relatórios gerados.
