# API e dashboard: rodar e publicar

As duas aplicações rodam localmente pelo `.venv` ou pelo `docker compose`, e as duas podem ser publicadas de
graça. O projeto não mantém uma instância pública.

## API de inferência

FastAPI que prevê, no checkout, se um pedido vai atrasar e em quantos dias vai chegar. Com os modelos treinados
(`make up`, `make ingest`, `make dbt-build`, `make train`):

```bash
make export-model   # campeões do MLflow + lookup de CEPs em models_export/
make api            # pelo .venv, em http://localhost:8000/docs
make api-docker     # ou pelo docker compose (perfil api), na mesma porta
```

Na inicialização, a API tenta o MLflow (`MLFLOW_TRACKING_URI`) e serve os `champion` atuais. Se o MLflow não
responder, usa o pacote de `models_export/` (`API_BUNDLE_DIR`); o `/model-info` mostra qual foi usado.

| Rota | O que faz |
|---|---|
| `GET /health` | 200 com o modelo carregado; 503 se o carregamento falhou |
| `GET /model-info` | Versões, limiar, origem do modelo e data do snapshot dos vendedores |
| `POST /predict` | Um pedido |
| `POST /predict/batch` | Até 1.000 pedidos, na mesma ordem |

O contrato completo, com exemplo pronto, está no Swagger (`/docs`). O que importa para usar a resposta:

- **Só entra o que se sabe no checkout.** Campos posteriores à compra (aprovação, envio, avaliação) voltam 422.
- **`late_risk_score` ordena pedidos por risco, mas não é uma probabilidade calibrada.** `is_late_predicted`
  compara o score com o limiar escolhido na validação.
- **Pedidos antigos.** O histórico do vendedor é uma fotografia do último treino. Uma compra anterior a ela
  recebe um aviso, porque a fotografia já inclui entregas posteriores. Para avaliar pedidos passados, use o
  pipeline de treino (histórico *point-in-time*), não a API.

## Dashboard

App Streamlit sobre os marts, com 8 páginas:

| Página | O que mostra |
|---|---|
| Visão geral de SLA | Entregas, % com atraso, prazo real e prometido, nota média; atraso e volume por mês |
| Demanda e receita | Receita entregue e a parte que chegou com atraso, demanda por dia × hora, peso do frete por distância, aprovação do pagamento |
| Rotas e vendedores | Mapa de arcos UF → UF, rotas e UFs com mais atraso, vendedores (atraso × nota) |
| Categorias, frete e distância | Atraso por categoria, faixa de frete e faixa de distância |
| Atraso × Avaliação | Nota por faixa de atraso e quanto os comentários falam da entrega |
| Coortes | Prazo e nota por mês; recompra em 180 dias conforme a primeira entrega |
| Qualidade dos dados | Anomalias da fonte, violações contadas pelo dbt e o tratamento de cada uma |
| Monitoramento do modelo | Simulação de produção: desempenho mensal, *drift* e decisões de retreino |

Os filtros da barra lateral (mês de compra e região do cliente) valem para as páginas de análise. O período
padrão é 2017-01 a 2018-08, porque as pontas da série têm poucos pedidos ([`dados.md`](dados.md)).

```bash
make dashboard          # pelo .venv, em http://localhost:8501 (exige make dbt-build)
make dashboard-docker   # ou pelo docker compose (perfil dashboard), na mesma porta
make extract            # extrato Parquet em data/extract/, para rodar sem banco:
DASHBOARD_SOURCE=parquet make dashboard
```

`DASHBOARD_PARQUET_LOCATION` aponta para uma pasta local (padrão `data/extract`) ou para a URL base dos arquivos.

## Publicar

**Licença primeiro.** O pacote dos modelos e o extrato derivam do dataset da Olist (CC BY-NC-SA 4.0): uma
publicação precisa ser não comercial, citar a fonte e manter a licença.

### API no Hugging Face Spaces

A imagem traz o pacote dos modelos embutido, então roda sem MLflow nem Postgres.

1. Gere a imagem com o campeão atual: `make api-docker`.
2. Publique no GHCR com um *personal access token* (classic) com `write:packages`:

   ```bash
   docker login ghcr.io -u mathewsca
   docker tag olist-api:local ghcr.io/mathewsca/olist-api:v1
   docker push ghcr.io/mathewsca/olist-api:v1
   ```

   Depois, torne o pacote público em *GitHub → Packages → olist-api → Package settings*. O `release.yml` faz o
   mesmo a cada Release (`make release-bundle` gera o anexo `dist/models_export.tar.gz`).
3. Crie um Space (SDK **Docker**, hardware **CPU basic**) com dois arquivos: um `Dockerfile` com a linha
   `FROM ghcr.io/mathewsca/olist-api:v1` e um `README.md` com o cabeçalho do Spaces (`sdk: docker`,
   `app_port: 8000`, `license: cc-by-nc-sa-4.0`) e a atribuição do dataset.
4. Confira `https://<usuario>-<space>.hf.space/model-info`: `served_from` deve ser `export`.

Medição local de 2026-10-30 (`docker stats`, modelo carregado): 231 MiB de memória; a imagem ocupa 1,1 GB.

### Dashboard no Streamlit Community Cloud

O Cloud não alcança o Postgres local, então o app lê o extrato por URL. Este caminho ainda não foi validado.

1. `make extract` e anexe os arquivos de `data/extract/` a uma Release (por exemplo, a tag `data-v1`).
2. Crie o app apontando para `dashboard/app.py`, com `DASHBOARD_SOURCE = "parquet"` e
   `DASHBOARD_PARQUET_LOCATION` = URL base da Release.
3. Um `requirements.txt` na raiz com a linha `.[dashboard]` instala o pacote.
