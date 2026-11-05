# Changelog

Mudanças relevantes do projeto. Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/);
versões seguem o [Versionamento Semântico](https://semver.org/lang/pt-BR/).

## [1.0.0] - não publicada

Primeira versão completa da plataforma, da ingestão ao modelo monitorado.

### Adicionado

- **Fundação:** pacote `olist_platform` em `src/`, extras de dependência por componente, ruff, pytest,
  pre-commit, Makefile e CI (lint + testes em Python 3.11 e 3.12).
- **Ingestão:** download idempotente do Kaggle, carga atômica dos 9 CSVs no schema `raw` com linhagem e checagens
  de qualidade; Postgres 17 e Airflow 3 (LocalExecutor) no Docker Compose; DAG `olist_ingestion`.
- **Transformação:** projeto dbt com camadas `staging`, `intermediate` e `marts` (`fct_deliveries`,
  `fct_orders`, `fct_order_items` e dimensões), testes genéricos e de regra de negócio; documentação e
  linhagem publicadas no GitHub Pages.
- **Análise:** 14 análises em `dbt/analyses/` (SLA, rotas, receita, sazonalidade, frete, pagamento, avaliações e
  vendedores) com relatório gerado (`docs/analises.md`) e dashboard Streamlit com 8 páginas, lendo o Postgres ou
  um extrato Parquet.
- **Qualidade dos dados:** anomalias conhecidas da fonte como testes dbt `warn`, com o tratamento de cada uma
  numa seed (`data_issues`) e as contagens no relatório e no dashboard.
- **Modelagem:** classificador de atraso e regressor de prazo com features compartilhadas entre treino e API,
  histórico do vendedor *point-in-time*, divisão temporal, baselines, SHAP e registro no MLflow.
- **API:** FastAPI com `/predict` e `/predict/batch`, modelo carregado do MLflow com fallback para um pacote
  exportado, imagem Docker multi-stage e testes de contrato.
- **MLOps:** simulação de produção de 2018-04 a 2018-08 com *drift* (Evidently), desempenho mensal, gatilhos de
  retreino e *quality gate*, com o relatório de *drift* de cada mês guardado no MLflow; DAG `olist_monitoring_retrain`; model card; workflow de release que publica as
  imagens da API e do dashboard no GHCR.

[1.0.0]: https://github.com/mathewsca/olist-logistics-platform/releases/tag/v1.0.0
