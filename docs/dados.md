# Dados

## Fonte

- **Dataset:** [Brazilian E-Commerce Public Dataset by Olist](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce)
  (Kaggle: `olistbr/brazilian-ecommerce`).
- **Licença:** CC BY-NC-SA 4.0 (campo `licenseName` da API do Kaggle, consultado em 2026-10-15). Uso não comercial,
  com atribuição — compatível com um projeto de portfólio. Os dados **não** são redistribuídos neste repositório.
- **Período:** compras de 2016-09-04 a 2018-10-17 (`min`/`max` de `order_purchase_timestamp` em `raw.orders`,
  carga de 2026-10-15).
- **Acesso:** API do Kaggle com as credenciais do `.env` (`KAGGLE_USERNAME` + `KAGGLE_KEY`, ou `KAGGLE_API_TOKEN`).
  O download é idempotente e grava em `data/landing/` (ignorado pelo git).

## Arquivos

| Arquivo | Conteúdo | Grão | Linhas |
|---|---|---|--:|
| `olist_orders_dataset` | Pedido: status e datas de compra, aprovação, envio, entrega e prazo estimado | pedido | 99.441 |
| `olist_order_items_dataset` | Itens do pedido: produto, vendedor, preço, frete e prazo limite de envio | item do pedido | 112.650 |
| `olist_order_payments_dataset` | Pagamentos: tipo, parcelas e valor | pagamento do pedido | 103.886 |
| `olist_order_reviews_dataset` | Avaliações: nota, comentário e datas | avaliação | 99.224 |
| `olist_customers_dataset` | Clientes: id único, prefixo do CEP, cidade e UF | cliente por pedido | 99.441 |
| `olist_sellers_dataset` | Vendedores: prefixo do CEP, cidade e UF | vendedor | 3.095 |
| `olist_products_dataset` | Produtos: categoria (em português), peso e dimensões | produto | 32.951 |
| `olist_geolocation_dataset` | Prefixo do CEP → lat/lng (várias linhas por prefixo) | ponto geográfico | 1.000.163 |
| `product_category_name_translation` | Tradução da categoria para inglês | categoria | 71 |

Linhas = registros carregados em `raw` na carga de 2026-10-15, iguais aos registros de cada CSV (checagem
automática da ingestão).

Pontos de atenção (medidos na carga de 2026-10-15):

- `customer_id` é gerado por pedido: 99.441 ids para 96.096 `customer_unique_id`. Coortes e recorrência
  usam `customer_unique_id`.
- A geolocalização tem 1.000.163 linhas para 19.015 prefixos de CEP, por isso a deduplicação por prefixo no dbt.
- `review_id` não é único (99.224 linhas, 98.410 ids) e 547 pedidos têm mais de uma avaliação; o pedido usa
  a avaliação mais recente.
- Duas categorias de produto não têm tradução (`pc_gamer` e `portateis_cozinha_e_preparadores_de_alimentos`) e
  610 produtos não têm categoria.
- 3.852 comentários de avaliação têm quebra de linha dentro das aspas; a contagem usa o parser de CSV.
- `product_category_name_translation.csv` começa com BOM UTF-8; a checagem de cabeçalho o ignora.
- `order_status`: 96.478 `delivered`, 1.107 `shipped`, 625 `canceled`, 609 `unavailable`, 314 `invoiced`,
  301 `processing`, 5 `created` e 2 `approved`. Só pedidos entregues entram em `fct_deliveries` e na modelagem.
- Colunas de data posteriores à compra (aprovação, envio, entrega, avaliação) **não podem** ser features
  (a lista de colunas excluídas e o motivo está no [model card](model_card.md)).

## Qualidade e volumes

Cada anomalia conhecida da fonte tem um teste dbt com severidade `warn`, que conta as violações e guarda as linhas
no schema `audit`; o tratamento de cada uma fica na seed `dbt/seeds/data_issues.csv`. As contagens atuais estão na
seção "Qualidade dos dados" de [`analises.md`](analises.md) e na página de mesmo nome do dashboard.

Volumes dos marts no `dbt build` de 2026-10-21:

| Tabela | Linhas |
|---|--:|
| `fct_orders` | 99.441 |
| `fct_order_items` | 112.650 |
| `fct_deliveries` | 96.470 |
| `dim_customers` | 99.441 |
| `dim_sellers` | 3.095 |
| `dim_products` | 32.951 |
| `dim_geography` | 19.011 |
| `dim_date` | 1.096 |

Em `fct_deliveries`, 1.275 pedidos (1,3%) têm mais de um vendedor. Neles, a origem é o vendedor do item mais caro. Outros 477 ficam sem `distance_km`. A geolocalização tem 19.015 prefixos
na fonte: 19.011 restam depois de descartar os pontos fora do Brasil, porque 4 prefixos só tinham pontos fora.

## Janelas temporais

O dataset é histórico, então "produção" é simulada no tempo. Cortes adotados (pela data da compra):

| Uso | Janela |
|---|---|
| Treino | 2017-01 a 2018-03 |
| Validação | 2018-04 e 2018-05 (escolha do campeão e do limiar) |
| Teste | 2018-06 a 2018-08, olhado uma vez |
| Simulação de produção | 2018-04 a 2018-08, um mês por vez, com um campeão próprio treinado só com o que se sabia em 2018-04-01 |

Volume de pedidos por mês de compra (`raw.orders`, carga de 2026-10-15):

| Período | Pedidos/mês | Observação |
|---|---|---|
| 2016-09 a 2016-12 | 4, 324, 0, 1 | Início do registro; novembro de 2016 não tem pedidos |
| 2017-01 a 2017-10 | 800 a 4.631 | Tendência de alta, com quedas em abril e junho |
| 2017-11 | 7.544 | Pico da série (mês da Black Friday) |
| 2017-12 a 2018-08 | 5.673 a 7.269 | Patamar estável |
| 2018-09 e 2018-10 | 16 e 4 | Fim do registro: 19 dos 20 pedidos estão `canceled` e 1 `shipped` |

As pontas (2016 e set–out de 2018) são esparsas demais para treino ou monitoramento, por isso a população da
modelagem vai de 2017-01 a 2018-08.
