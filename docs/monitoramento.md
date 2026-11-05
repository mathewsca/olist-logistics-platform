# Monitoramento e retreino

Resultados de `make monitor` executado em 2026-11-05 sobre os marts com os dados reais. Este arquivo é gerado: não edite à mão.

## Como a simulação funciona

Os meses de 2018-04 a 2018-08 fazem o papel de produção, um de cada vez. O primeiro campeão só viu o que era conhecido em 2018-04-01. Cada mês é avaliado 1 mês depois de fechar, quando a maioria das entregas já chegou.

Retreino quando qualquer gatilho dispara:

- *drift* (Evidently) em pelo menos 50% das features;
- lift abaixo de 75% do lift da validação do campeão;
- MAE acima de 125% do MAE da validação do campeão.

No gate, a receita de retreino ajustada com o que se sabia no início do mês enfrenta o par que serviu o mês. Ela passa se tiver, nesse mês, PR-AUC pelo menos 5% acima do campeão e acima da regra da rota, MAE não pior e pelo menos 30 atrasos para comparar; então é reajustada com tudo o que se sabe na avaliação e promovida. Os modelos ficam em `olist-late-delivery-sim` e `olist-delivery-days-sim`, separados dos que a API serve.

## Mês a mês

Métricas do campeão que estava em produção no início de cada mês, sobre os pedidos daquele mês que já tinham sido entregues na data da avaliação. Lift = PR-AUC ÷ taxa de atraso (1 = aleatório); entre parênteses, o valor do mesmo modelo na sua validação.

| mês | avaliado_em | campeão | pedidos | com_rótulo | atraso_pct | pr_auc | lift (validação) | recall_pct | sinalizados_pct | mae_dias (validação) | drift_pct | retreino | gate |
|---|---|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|---|
| 2018-04 | 2018-06-01 | v1 | 6.798 | 6.715 | 3,4 | 0,129 | 3,75 (2,25) | 69,1 | 26,4 | 4,85 (5,37) | 23,5 | não | - |
| 2018-05 | 2018-07-01 | v1 | 6.749 | 6.726 | 6,3 | 0,129 | 2,03 (2,25) | 61,1 | 37,2 | 4,65 (5,37) | 41,2 | não | - |
| 2018-06 | 2018-08-01 | v1 | 6.096 | 6.070 | 0,8 | 0,041 | 4,90 (2,25) | 80,4 | 29,7 | 4,65 (5,37) | 35,3 | não | - |
| 2018-07 | 2018-09-01 | v1 | 6.156 | 6.138 | 3,1 | 0,059 | 1,89 (2,25) | 78,4 | 64,8 | 4,24 (5,37) | 35,3 | não | - |
| 2018-08 | 2018-10-01 | v1 | 6.351 | 6.351 | 6,2 | 0,096 | 1,55 (2,25) | 95,7 | 84,2 | 3,64 (5,37) | 47,1 | sim | v2 rejeitado |

## Retreinos e quality gate

- **2018-08**: retreino por PR-AUC lift 1.55 vs 2.25 on validation.
  Gate: v2 rejeitado. PR-AUC challenger 0.078 vs champion 0.092 (route rule 0.157); MAE 3.59 vs 3.43. PR-AUC 0.078 not 5% above the champion's 0.092; PR-AUC 0.078 not above the route rule 0.157; MAE 3.59 worse than the champion's 3.43.

## Por região do cliente (2018-08)

Recall e PR-AUC só com pelo menos 10 atrasos na região.

| região | pedidos | atraso_pct | sinalizados_pct | recall_pct | pr_auc |
|---|--:|--:|--:|--:|--:|
| Centro-Oeste | 334 | 5,4 | 83,2 | 100,0 | 0,077 |
| Nordeste | 433 | 2,1 | 94,7 | - | - |
| Norte | 73 | 2,7 | 82,2 | - | - |
| Sudeste | 4.690 | 7,2 | 83,9 | 95,6 | 0,119 |
| Sul | 821 | 3,0 | 80,6 | 92,0 | 0,077 |

## Relatório de drift

O relatório do Evidently de cada mês (features servidas × referência do treino do campeão) fica no MLflow, no run `evaluate-AAAA-MM` do experimento `olist-monitoring-simulation`. Ficam fora da fração de drift `purchase_month` (um único mês sempre difere de uma referência de um ano inteiro) e o histórico do vendedor (o snapshot servido para de crescer, então o drift dele mediria só a idade do snapshot).
