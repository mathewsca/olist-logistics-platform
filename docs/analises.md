# Análises de logística

Resultados das consultas em `dbt/analyses/`, executadas em 2026-11-05 sobre os marts com os dados reais. Este arquivo é gerado por `make analyses`: não edite à mão. Os números do README saem daqui.

População: `fct_deliveries` (pedidos entregues com data de entrega). Atraso = entregue depois da data prometida pela Olist (datas de calendário). Percentuais em `_pct`; dias em `_days`.

## Taxa de atraso por mês de compra

Entregas, % entregue depois da data prometida, atraso médio dos atrasados e prazo mediano. Consulta: `dbt/analyses/monthly_late_rate.sql`.

| year_month | deliveries | late_pct | avg_days_late_when_late | median_delivery_days |
|---|--:|--:|--:|--:|
| 2016-09 | 1 | 100,0 | 36,0 | 54,8 |
| 2016-10 | 265 | 0,8 | 9,5 | 17,9 |
| 2016-12 | 1 | 0,0 |  | 4,7 |
| 2017-01 | 750 | 2,9 | 20,2 | 10,7 |
| 2017-02 | 1.653 | 3,0 | 20,8 | 11,0 |
| 2017-03 | 2.546 | 4,6 | 25,4 | 10,1 |
| 2017-04 | 2.303 | 6,6 | 12,3 | 12,8 |
| 2017-05 | 3.545 | 3,0 | 12,5 | 9,8 |
| 2017-06 | 3.135 | 3,0 | 14,3 | 10,8 |
| 2017-07 | 3.872 | 2,8 | 11,7 | 10,2 |
| 2017-08 | 4.193 | 2,9 | 8,8 | 9,8 |
| 2017-09 | 4.150 | 4,4 | 9,4 | 10,3 |
| 2017-10 | 4.478 | 4,2 | 9,2 | 10,3 |
| 2017-11 | 7.288 | 12,4 | 11,2 | 12,7 |
| 2017-12 | 5.513 | 7,5 | 9,7 | 13,1 |
| 2018-01 | 7.069 | 5,7 | 11,9 | 11,8 |
| 2018-02 | 6.555 | 14,1 | 12,6 | 14,3 |
| 2018-03 | 7.003 | 19,0 | 10,0 | 13,4 |
| 2018-04 | 6.798 | 4,5 | 10,4 | 9,3 |
| 2018-05 | 6.749 | 6,6 | 7,1 | 9,2 |
| 2018-06 | 6.096 | 1,2 | 13,4 | 8,0 |
| 2018-07 | 6.156 | 3,4 | 8,4 | 7,5 |
| 2018-08 | 6.351 | 6,2 | 4,4 | 7,0 |

## Receita entregue por mês de compra

Itens + frete dos pedidos entregues; `late_revenue_pct` é a parte dessa receita que chegou com atraso. Consulta: `dbt/analyses/monthly_revenue.sql`.

| year_month | deliveries | revenue_brl | avg_ticket_brl | freight_share_pct | late_revenue_pct |
|---|--:|--:|--:|--:|--:|
| 2016-09 | 1 | 143 | 143,46 | 5,9 | 100,0 |
| 2016-10 | 265 | 46.491 | 175,44 | 13,3 | 0,4 |
| 2016-12 | 1 | 20 | 19,62 | 44,4 | 0,0 |
| 2017-01 | 750 | 127.482 | 169,98 | 12,3 | 2,8 |
| 2017-02 | 1.653 | 271.239 | 164,09 | 13,6 | 2,7 |
| 2017-03 | 2.546 | 414.331 | 162,74 | 13,3 | 4,7 |
| 2017-04 | 2.303 | 390.812 | 169,70 | 12,8 | 8,2 |
| 2017-05 | 3.545 | 566.657 | 159,85 | 13,7 | 3,0 |
| 2017-06 | 3.135 | 490.050 | 156,32 | 13,9 | 5,9 |
| 2017-07 | 3.872 | 566.299 | 146,25 | 15,0 | 3,8 |
| 2017-08 | 4.193 | 645.832 | 154,03 | 14,1 | 3,0 |
| 2017-09 | 4.150 | 701.077 | 168,93 | 13,4 | 4,5 |
| 2017-10 | 4.478 | 751.117 | 167,73 | 13,7 | 4,0 |
| 2017-11 | 7.288 | 1.153.229 | 158,24 | 14,4 | 12,9 |
| 2017-12 | 5.513 | 843.078 | 152,93 | 13,9 | 10,4 |
| 2018-01 | 7.069 | 1.077.887 | 152,48 | 14,2 | 7,4 |
| 2018-02 | 6.555 | 966.168 | 147,39 | 14,5 | 15,5 |
| 2018-03 | 7.003 | 1.120.598 | 160,02 | 14,9 | 19,8 |
| 2018-04 | 6.798 | 1.132.879 | 166,65 | 14,1 | 5,1 |
| 2018-05 | 6.749 | 1.128.775 | 167,25 | 13,4 | 6,8 |
| 2018-06 | 6.096 | 1.011.449 | 165,92 | 15,4 | 1,5 |
| 2018-07 | 6.156 | 1.027.287 | 166,88 | 15,6 | 4,1 |
| 2018-08 | 6.351 | 985.492 | 155,17 | 14,9 | 6,0 |

## Demanda e atraso por dia da semana da compra

Volume, atraso e dias da compra ao envio à transportadora (`seller_handling_days`). Consulta: `dbt/analyses/late_rate_by_purchase_weekday.sql`.

| purchase_weekday | deliveries | late_pct | avg_seller_handling_days | avg_delivery_days |
|---|--:|--:|--:|--:|
| 1. Monday | 15.701 | 7,4 | 2,71 | 12,00 |
| 2. Tuesday | 15.502 | 7,1 | 2,84 | 12,08 |
| 3. Wednesday | 15.074 | 6,6 | 2,99 | 12,44 |
| 4. Thursday | 14.322 | 6,3 | 3,37 | 12,74 |
| 5. Friday | 13.684 | 7,0 | 4,21 | 13,57 |
| 6. Saturday | 10.555 | 6,6 | 3,87 | 13,36 |
| 7. Sunday | 11.632 | 6,2 | 2,84 | 11,96 |

## Rotas UF → UF mais movimentadas

As 20 rotas com mais entregas (mínimo de 300), com atraso, distância, prazo prometido e real. Consulta: `dbt/analyses/route_state_pairs.sql`.

| origin_state | destination_state | deliveries | late_pct | avg_distance_km | avg_promised_days | avg_delivery_days |
|---|---|--:|--:|--:|--:|--:|
| SP | SP | 30.722 | 4,6 | 150 | 18,0 | 7,9 |
| SP | RJ | 8.154 | 14,1 | 441 | 27,0 | 16,3 |
| SP | MG | 7.438 | 5,3 | 495 | 25,0 | 12,4 |
| SP | RS | 3.593 | 6,6 | 906 | 30,3 | 16,2 |
| SP | PR | 3.117 | 4,4 | 463 | 25,8 | 12,8 |
| PR | SP | 2.928 | 3,1 | 470 | 26,2 | 11,2 |
| MG | SP | 2.549 | 3,6 | 418 | 24,4 | 10,9 |
| SP | SC | 2.326 | 9,5 | 562 | 26,7 | 15,8 |
| SP | BA | 2.307 | 12,9 | 1.389 | 30,5 | 19,8 |
| MG | MG | 1.526 | 2,5 | 259 | 21,1 | 8,7 |
| SP | ES | 1.459 | 12,3 | 785 | 25,3 | 15,8 |
| SP | GO | 1.421 | 7,5 | 748 | 27,5 | 16,0 |
| SP | DF | 1.382 | 6,4 | 807 | 24,7 | 13,3 |
| RJ | SP | 1.320 | 7,8 | 402 | 23,4 | 11,8 |
| SC | SP | 1.313 | 3,7 | 512 | 26,6 | 12,1 |
| MG | RJ | 1.138 | 8,3 | 371 | 27,5 | 14,2 |
| SP | PE | 1.131 | 9,8 | 2.049 | 32,5 | 18,9 |
| PR | RJ | 970 | 12,1 | 843 | 30,3 | 17,3 |
| SP | CE | 969 | 13,7 | 2.258 | 32,1 | 21,2 |
| RJ | RJ | 955 | 4,7 | 55 | 19,6 | 6,6 |

## Atraso por categoria de produto

Categorias com pelo menos 1.000 entregas, da maior para a menor taxa de atraso. Consulta: `dbt/analyses/late_rate_by_category.sql`.

| product_category | deliveries | late_pct | avg_freight_value | avg_distance_km |
|---|--:|--:|--:|--:|
| baby | 2.761 | 8,1 | 24,15 | 608 |
| office_furniture | 1.251 | 8,1 | 53,67 | 564 |
| electronics | 2.502 | 7,7 | 18,27 | 627 |
| bed_bath_table | 9.184 | 7,5 | 22,02 | 513 |
| health_beauty | 8.613 | 7,5 | 20,79 | 680 |
| watches_gifts | 5.476 | 7,4 | 17,98 | 647 |
| auto | 3.792 | 7,3 | 23,85 | 619 |
| furniture_decor | 6.188 | 7,2 | 27,04 | 567 |
| unknown | 1.358 | 7,1 | 19,83 | 556 |
| telephony | 4.073 | 7,1 | 16,98 | 697 |
| perfumery | 3.069 | 6,6 | 17,21 | 577 |
| sports_leisure | 7.492 | 6,6 | 21,78 | 597 |
| stationery | 2.244 | 6,6 | 20,39 | 561 |
| garden_tools | 3.400 | 6,6 | 28,12 | 649 |
| computers_accessories | 6.511 | 6,4 | 22,14 | 677 |
| toys | 3.787 | 6,4 | 20,10 | 563 |
| consoles_games | 1.013 | 6,1 | 18,80 | 724 |
| cool_stuff | 3.530 | 5,9 | 23,14 | 654 |
| fashion_bags_accessories | 1.811 | 5,6 | 16,88 | 584 |
| housewares | 5.680 | 5,4 | 25,10 | 494 |
| pet_shop | 1.682 | 5,1 | 23,23 | 560 |
| luggage_accessories | 1.012 | 4,2 | 29,70 | 560 |

## Atraso por faixa de frete (R$)

Frete total do pedido. Consulta: `dbt/analyses/late_rate_by_freight.sql`.

| freight_band | deliveries | late_pct | avg_distance_km |
|---|--:|--:|--:|
| 1. < 10 | 11.062 | 4,3 | 73 |
| 2. 10-15 | 19.511 | 5,0 | 274 |
| 3. 15-20 | 32.840 | 7,5 | 613 |
| 4. 20-30 | 16.348 | 7,7 | 913 |
| 5. 30-50 | 10.604 | 8,1 | 968 |
| 6. >= 50 | 6.105 | 8,6 | 1.061 |

## Atraso por faixa de distância vendedor → cliente (km)

Distância em linha reta; `unknown` = prefixo de CEP sem geolocalização. Consulta: `dbt/analyses/late_rate_by_distance.sql`.

| distance_band | deliveries | late_pct | avg_promised_days | avg_delivery_days |
|---|--:|--:|--:|--:|
| 1. < 100 | 17.887 | 4,5 | 16,0 | 6,5 |
| 2. 100-300 | 13.356 | 5,2 | 21,4 | 10,0 |
| 3. 300-600 | 31.496 | 6,8 | 25,0 | 12,6 |
| 4. 600-1000 | 17.911 | 7,1 | 27,5 | 14,7 |
| 5. 1000-2000 | 9.728 | 9,5 | 30,8 | 18,0 |
| 6. >= 2000 | 5.615 | 12,0 | 33,8 | 21,2 |
| 7. unknown | 477 | 9,4 | 24,9 | 14,4 |

## Peso do frete por faixa de distância (km)

Mediana de frete ÷ valor dos itens, em %. Consulta: `dbt/analyses/freight_share_by_distance.sql`.

| distance_band | deliveries | avg_freight_value | median_freight_share_pct |
|---|--:|--:|--:|
| 1. < 100 | 17.887 | 13,44 | 17,2 |
| 2. 100-300 | 13.356 | 18,75 | 18,9 |
| 3. 300-600 | 31.496 | 22,40 | 23,0 |
| 4. 600-1000 | 17.911 | 24,81 | 25,3 |
| 5. 1000-2000 | 9.728 | 33,09 | 28,4 |
| 6. >= 2000 | 5.615 | 39,87 | 34,0 |
| 7. unknown | 477 | 24,15 | 23,6 |

## Pagamento, aprovação e atraso

Forma de pagamento de maior valor no pedido; horas da compra à aprovação (mediana). Consulta: `dbt/analyses/late_rate_by_payment_type.sql`.

| payment_type | deliveries | median_approval_hours | avg_delivery_days | late_pct |
|---|--:|--:|--:|--:|
| credit_card | 72.818 | 0,3 | 12,35 | 6,7 |
| boleto | 19.191 | 29,1 | 13,49 | 7,3 |
| voucher | 2.977 | 0,3 | 12,51 | 6,0 |
| debit_card | 1.483 | 0,8 | 10,79 | 5,3 |
| unknown | 1 | 0,0 | 54,81 | 100,0 |

## Avaliação por faixa de atraso

Nota média e % de notas 1–2 entre as entregas avaliadas. Consulta: `dbt/analyses/late_vs_review.sql`.

| delay_band | reviewed_deliveries | avg_review_score | low_score_pct |
|---|--:|--:|--:|
| 1. 15+ days early | 34.771 | 4,32 | 9,0 |
| 2. 8-14 days early | 36.158 | 4,31 | 8,9 |
| 3. 1-7 days early | 17.234 | 4,20 | 10,2 |
| 4. on the promised day | 1.280 | 4,03 | 12,4 |
| 5. 1-3 days late | 1.852 | 3,29 | 32,1 |
| 6. 4-7 days late | 1.748 | 2,10 | 67,7 |
| 7. 8-14 days late | 1.446 | 1,67 | 80,2 |
| 8. 15+ days late | 1.335 | 1,72 | 78,4 |

## O que dizem os comentários das avaliações

Avaliações com comentário; `mentions_delivery_pct` = o texto cita entrega, prazo, atraso, recebimento, correios ou transportadora. Consulta: `dbt/analyses/review_comments_by_score.sql`.

| score_group | comments | mentions_delivery_pct | late_pct |
|---|--:|--:|--:|
| 1. 1-2 | 9.234 | 65,5 | 29,7 |
| 2. 3 | 3.431 | 50,3 | 10,2 |
| 3. 4-5 | 26.224 | 49,5 | 2,5 |

## Vendedores: taxa de atraso × nota

Vendedores com pelo menos 30 entregas, por faixa da sua taxa de atraso (%). Consulta: `dbt/analyses/seller_late_vs_review.sql`.

| seller_late_band | sellers | deliveries | avg_review_score |
|---|--:|--:|--:|
| 1. < 5 | 277 | 27.064 | 4,27 |
| 2. 5-10 | 215 | 40.742 | 4,13 |
| 3. 10-20 | 117 | 11.966 | 3,97 |
| 4. >= 20 | 13 | 642 | 3,51 |

## Folga do prazo prometido por UF do cliente

Folga = dias prometidos − dias reais. A primeira linha (`all`) é o total. Consulta: `dbt/analyses/estimate_bias.sql`.

| destination_state | deliveries | avg_promised_days | avg_delivery_days | median_slack_days | early_7_plus_pct | late_pct |
|---|--:|--:|--:|--:|--:|--:|
| all | 96.470 | 24,4 | 12,6 | 12,4 | 75,9 | 6,8 |
| AC | 80 | 41,7 | 21,0 | 21,8 | 91,3 | 3,8 |
| AP | 67 | 46,9 | 27,2 | 21,8 | 95,5 | 3,0 |
| RO | 243 | 39,4 | 19,4 | 20,7 | 92,6 | 2,9 |
| RR | 41 | 46,6 | 29,4 | 19,7 | 78,0 | 12,2 |
| AM | 145 | 45,9 | 26,4 | 18,9 | 88,3 | 2,8 |
| PA | 946 | 37,8 | 23,8 | 15,6 | 77,8 | 11,2 |
| RN | 474 | 32,9 | 19,3 | 15,1 | 79,1 | 9,3 |
| MT | 886 | 32,4 | 18,1 | 14,9 | 82,3 | 6,0 |
| RS | 5.344 | 29,2 | 15,3 | 14,6 | 81,4 | 6,1 |
| PE | 1.593 | 31,7 | 18,4 | 14,3 | 78,0 | 9,6 |
| PB | 517 | 33,6 | 20,4 | 14,1 | 77,6 | 10,4 |
| MG | 11.354 | 25,2 | 12,0 | 13,7 | 82,6 | 4,6 |
| PR | 4.923 | 25,3 | 12,0 | 13,6 | 82,8 | 4,0 |
| PI | 476 | 30,7 | 19,5 | 13,5 | 68,5 | 13,9 |
| TO | 274 | 29,7 | 17,7 | 13,3 | 75,2 | 9,9 |
| GO | 1.957 | 27,7 | 15,6 | 13,0 | 76,9 | 6,5 |
| CE | 1.279 | 32,0 | 21,3 | 12,9 | 70,7 | 13,8 |
| RJ | 12.350 | 27,0 | 15,3 | 12,9 | 73,3 | 12,1 |
| SE | 335 | 31,5 | 21,5 | 12,8 | 69,9 | 15,2 |
| SC | 3.546 | 26,4 | 15,0 | 12,6 | 74,4 | 8,2 |
| DF | 2.080 | 24,9 | 13,0 | 12,6 | 77,5 | 5,7 |
| BA | 3.256 | 30,1 | 19,3 | 12,3 | 72,1 | 12,2 |
| MS | 701 | 26,6 | 15,6 | 12,1 | 72,6 | 9,7 |
| ES | 1.995 | 26,2 | 15,8 | 11,8 | 72,8 | 10,7 |
| SP | 40.494 | 19,8 | 8,8 | 11,0 | 73,9 | 4,5 |
| MA | 717 | 31,1 | 21,6 | 10,5 | 62,9 | 17,4 |
| AL | 397 | 33,2 | 24,5 | 10,2 | 58,4 | 21,4 |

## Recompra em 180 dias conforme a primeira entrega

Clientes (`customer_unique_id`) cuja primeira compra entregue tem 180 dias de janela observada. Consulta: `dbt/analyses/repurchase_after_first_delivery.sql`.

| first_delivery | customers | repurchase_180d_pct |
|---|--:|--:|
| late | 3.778 | 2,46 |
| on time | 52.127 | 2,86 |

## Qualidade dos dados

Anomalias conhecidas da fonte. Cada uma tem um teste dbt com severidade `warn`, que conta as violações e guarda as linhas no schema `audit`; problema e tratamento vêm da seed `dbt/seeds/data_issues.csv`.

| problema | modelo | violações | tratamento |
|---|---|--:|---|
| Coordenadas de GPS fora do Brasil | `stg_olist__geolocation` | 31 | Descartadas antes da mediana por prefixo de CEP |
| Prefixo de CEP do cliente sem geolocalização | `dim_customers` | 279 | distance_km fica nulo e o modelo imputa |
| Prefixo de CEP do vendedor sem geolocalização | `dim_sellers` | 7 | distance_km fica nulo e o modelo imputa |
| Categoria sem tradução para o inglês | `stg_olist__products` | 13 | Mantém o nome em português |
| review_id compartilhado por mais de um pedido | `stg_olist__order_reviews` | 789 | A avaliação é escolhida por pedido (a mais recente) |
| Pedido entregue sem data de entrega | `stg_olist__orders` | 8 | Fica fora de fct_deliveries |
| Data de entrega em pedido não entregue | `stg_olist__orders` | 6 | Fica fora de fct_deliveries |
| Envio à transportadora antes da compra | `stg_olist__orders` | 166 | Mantido; seller_handling_days fica negativo |
| Entrega ao cliente antes do envio à transportadora | `stg_olist__orders` | 23 | Mantido; carrier_transit_days fica negativo |
| Valor pago difere de itens + frete em mais de R$ 1 | `fct_orders` | 249 | Mantido: juros de parcelamento e vouchers |
