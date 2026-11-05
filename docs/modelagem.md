# Modelagem preditiva

Resultados de `make train` executado em 2026-11-05 sobre os marts com os dados reais. Este arquivo é gerado: não edite à mão. Os números do README saem daqui. Alvos, features e colunas excluídas por vazamento: [model card](model_card.md).

## Divisão temporal

Por data da compra, do mais antigo ao mais recente. O limiar e o campeão são escolhidos na validação; o teste é olhado uma única vez.

| parte | compras | entregas | atraso_pct |
|---|---|--:|--:|
| treino | 2017-01-05 a 2018-03-31 | 64.053 | 8,0 |
| validação | 2018-04-01 a 2018-05-31 | 13.547 | 5,5 |
| teste | 2018-06-01 a 2018-08-29 | 18.603 | 3,6 |

## Classificação: o pedido vai atrasar?

Alvo `is_late` (entregue depois da data prometida). PR-AUC é a métrica principal, porque a classe positiva é rara; a PR-AUC de um classificador aleatório é a própria taxa de atraso. F1, precisão e recall usam o limiar que maximiza o F1 na validação. Brier só para probabilidades.

| método | parte | pr_auc | roc_auc | f1 | precision | recall | brier | sinalizados_pct |
|---|---|--:|--:|--:|--:|--:|--:|--:|
| Classe majoritária (= confiar no prazo da Olist) | validação | 0,055 | 0,500 | 0,000 | 0,000 | 0,000 | 0,053 | 0,0 |
| Classe majoritária (= confiar no prazo da Olist) | teste | 0,036 | 0,500 | 0,000 | 0,000 | 0,000 | 0,037 | 0,0 |
| Regra: mediana da rota − prazo prometido | validação | 0,099 | 0,677 | 0,177 | 0,110 | 0,454 | - | 22,8 |
| Regra: mediana da rota − prazo prometido | teste | 0,121 | 0,761 | 0,119 | 0,064 | 0,777 | - | 43,6 |
| **Regressão logística (classes balanceadas)** (campeão) | validação | 0,153 | 0,757 | 0,249 | 0,185 | 0,381 | 0,286 | 11,4 |
| **Regressão logística (classes balanceadas)** (campeão) | teste | 0,072 | 0,662 | 0,109 | 0,068 | 0,275 | 0,322 | 14,6 |
| LightGBM | validação | 0,128 | 0,681 | 0,187 | 0,139 | 0,283 | 0,051 | 11,2 |
| LightGBM | teste | 0,099 | 0,746 | 0,169 | 0,117 | 0,305 | 0,034 | 9,4 |
| LightGBM (classe positiva reponderada) | validação | 0,122 | 0,667 | 0,182 | 0,147 | 0,238 | 0,129 | 8,9 |
| LightGBM (classe positiva reponderada) | teste | 0,087 | 0,725 | 0,130 | 0,131 | 0,129 | 0,086 | 3,6 |

Campeão por PR-AUC na validação: `logistic_regression`, limiar 0,7775. Registrado como `olist-late-delivery` versão 5, alias `champion`.

## Regressão: em quantos dias o pedido chega?

Alvo `delivery_days` (da compra à entrega, em dias fracionários). Viés = média de (previsto − real): positivo significa prever mais dias do que a entrega levou.

| método | parte | mae_days | rmse_days | bias_days |
|---|---|--:|--:|--:|
| Prazo estimado da Olist | validação | 13,41 | 15,42 | 12,46 |
| Prazo estimado da Olist | teste | 13,29 | 15,94 | 12,81 |
| Mediana do treino | validação | 6,00 | 8,28 | 0,16 |
| Mediana do treino | teste | 5,21 | 6,54 | 2,99 |
| Mediana da rota UF → UF | validação | 4,72 | 7,00 | -0,25 |
| Mediana da rota UF → UF | teste | 4,45 | 5,86 | 2,47 |
| Regressão linear (Ridge) | validação | 5,86 | 7,61 | 3,29 |
| Regressão linear (Ridge) | teste | 6,39 | 7,81 | 5,39 |
| **LightGBM** (campeão) | validação | 5,02 | 6,97 | 1,44 |
| **LightGBM** (campeão) | teste | 4,36 | 5,85 | 2,75 |

Campeão por MAE na validação: `lightgbm`. Registrado como `olist-delivery-days` versão 5, alias `champion`.

## Calibração do classificador campeão (teste)

| decil | previsto_pct | observado_pct |
|--:|--:|--:|
| 1 | 16,4 | 0,4 |
| 2 | 29,9 | 1,5 |
| 3 | 38,3 | 2,3 |
| 4 | 45,5 | 2,8 |
| 5 | 51,8 | 3,6 |
| 6 | 57,7 | 3,7 |
| 7 | 63,5 | 4,2 |
| 8 | 69,9 | 4,4 |
| 9 | 77,4 | 5,5 |
| 10 | 87,6 | 7,8 |

## Explicabilidade (SHAP, `lightgbm`, teste)

Média do |SHAP| numa amostra do teste, em log-odds de atraso.

| feature | mean_abs_shap |
|---|--:|
| purchase_month | 0,6419 |
| estimated_delivery_days | 0,5503 |
| destination_state | 0,3232 |
| seller_prior_mean_delivery_days | 0,2460 |
| km_per_estimated_day | 0,1893 |
| origin_state | 0,1483 |
| main_product_category | 0,1430 |
| freight_value | 0,1292 |
| seller_prior_late_rate | 0,0862 |
| seller_prior_deliveries | 0,0696 |
| distance_km | 0,0613 |
| is_same_state | 0,0594 |
| items_value | 0,0458 |
| item_count | 0,0430 |
| total_weight_g | 0,0374 |

### Pedidos individuais

As cinco features que mais pesaram em cada pedido (SHAP positivo empurra para o atraso).

**atrasado com o maior risco previsto**: probabilidade prevista 51,6%, atrasou.

| feature | valor | shap |
|---|--:|--:|
| destination_state | BA | 1,126 |
| km_per_estimated_day | 60,37 | 0,645 |
| purchase_month | 7,00 | -0,586 |
| estimated_delivery_days | 21,00 | 0,501 |
| seller_prior_mean_delivery_days | 14,22 | 0,353 |

**atrasado com o menor risco previsto**: probabilidade prevista 0,7%, atrasou.

| feature | valor | shap |
|---|--:|--:|
| purchase_month | 7,00 | -0,656 |
| destination_state | PR | -0,450 |
| origin_state | PR | -0,299 |
| estimated_delivery_days | 30,00 | -0,297 |
| seller_prior_mean_delivery_days | 14,13 | 0,170 |

**entrega no prazo típica (risco mediano)**: probabilidade prevista 3,2%, chegou no prazo.

| feature | valor | shap |
|---|--:|--:|
| purchase_month | 6,00 | -0,731 |
| estimated_delivery_days | 30,00 | -0,413 |
| seller_prior_mean_delivery_days | 16,75 | 0,278 |
| seller_prior_deliveries | 444,00 | 0,162 |
| origin_state | SP | 0,114 |
