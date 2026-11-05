# Como contribuir

O fluxo abaixo é o mesmo usado para construir o projeto.

## Ambiente

```bash
cp .env.example .env   # credenciais do Kaggle e senha do warehouse
make setup             # .venv com todos os extras + hooks do pre-commit
make up                # Postgres, Airflow e MLflow
```

`make help` lista todos os comandos. O README explica como rodar o pipeline de ponta a ponta.

## Fluxo de trabalho

1. **Uma branch por mudança**, a partir da `main` atualizada, com prefixo do tipo: `feat/drift-report`,
   `fix/api-infinity`, `docs/model-card`.
2. **Commits pequenos em [Conventional Commits](https://www.conventionalcommits.org/pt-br/):**
   `<tipo>(<escopo>): <descrição>`, com os tipos `feat`, `fix`, `docs`, `refactor`, `perf`, `test`, `build`,
   `ci` e `chore`. A descrição fica em inglês, no imperativo e com até 72 caracteres. Os escopos são os
   componentes: `ingestion`, `dbt`, `analytics`, `dashboard`, `features`, `models`, `api`, `monitoring`,
   `airflow`, `docker`.
   - Mudanças não triviais levam um corpo explicando o porquê.
   - Mudanças incompatíveis usam `!` e o rodapé `BREAKING CHANGE:`.
3. **Pull Request** com o template preenchido. O CI precisa passar: `ci.yml` sempre, e `docs.yml` quando muda
   dbt, ingestão ou fixtures.
4. **Merge** depois da revisão. A branch é apagada em seguida.

## Qualidade

- `make lint` e `make test` antes de abrir o PR (o pre-commit já roda o ruff a cada commit).
- `make test-integration` quando a mudança toca banco, dbt, MLflow ou API (exige `make up`).
- Código, tabelas e colunas em inglês; documentação em português.
- Features só em `src/olist_platform/features/`, importadas pelo treino e pela API. Nada posterior à compra
  entra como feature (lista de colunas excluídas no [model card](docs/model_card.md)).
- **Nenhum número sem execução.** Números no README e em `docs/` saem de relatórios gerados (`make analyses`,
  `make train`, `make monitor`). Se ainda não rodou, use `TODO: preencher após execução`.
- Dados, credenciais e artefatos (`data/`, `.env`, `mlruns/`, `models_export/`, `dbt/target/`) nunca entram no
  git.

## Decisões

Decisões estruturais são explicadas na descrição do PR que as implementa. As duradouras entram, em uma
linha (decisão e motivo), na tabela "Decisões principais" do README.

## Release

1. Atualize o `CHANGELOG.md` (a versão e a data) e o `__version__` em `src/olist_platform/__init__.py`.
2. Gere o pacote dos modelos: `make train` (se preciso) e `make release-bundle`.
3. Crie a tag e a Release com o pacote anexado:

   ```bash
   gh release create v1.0.0 dist/models_export.tar.gz --title v1.0.0 --notes-file <notas>
   ```

4. O `release.yml` roda os testes e publica `olist-api` e `olist-dashboard` no GHCR com as tags `1.0.0`, `1.0` e
   `latest`.
