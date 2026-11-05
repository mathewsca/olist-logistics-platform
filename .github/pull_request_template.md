## O que muda

<!-- Uma ou duas frases. -->

## Por quê

<!-- Problema, decisão ou pendência que motivou a mudança. Link para a issue, se houver. -->

## Como verificar

<!-- Comandos e o resultado esperado (ex.: `make dbt-build` → PASS=152, WARN=7, ERROR=0). -->

## Checklist

- [ ] `make lint` e `make test` passam (e `make test-integration`, se mexe em banco, dbt, MLflow ou API)
- [ ] Números novos no README ou em `docs/` vêm de uma execução real (relatório gerado ou log)
- [ ] Nenhum dado, credencial ou artefato pesado no diff (`data/`, `.env`, `mlruns/`, `models_export/`)
- [ ] Decisão estrutural explicada acima e, se duradoura, na tabela de decisões do README; `CHANGELOG.md` atualizado
- [ ] Commits em Conventional Commits
