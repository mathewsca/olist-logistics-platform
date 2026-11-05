# Model card — previsão de atraso e prazo de entrega

Dois modelos servidos juntos pela API: um **classificador** de risco de atraso e um **regressor** de dias até a
entrega. Números de [`modelagem.md`](modelagem.md) (`make train` de 2026-11-05) e de
[`monitoramento.md`](monitoramento.md) (`make monitor`). Os dois relatórios trazem as tabelas completas.

## Resumo

| | Classificador | Regressor |
|---|---|---|
| Registro no MLflow | `olist-late-delivery`, alias `champion` | `olist-delivery-days`, alias `champion` |
| Algoritmo campeão | Regressão logística com classes balanceadas | LightGBM |
| Alvo | `is_late`: entregue depois da data prometida | `delivery_days`: da compra à entrega |
| Saída na API | `late_risk_score` (0–1) e `is_late_predicted` (score ≥ limiar 0,7775) | `predicted_delivery_days` (≥ 0) e `predicted_delivery_date` |
| Momento da previsão | No checkout, antes da aprovação do pagamento | Idem |

## Uso pretendido

- **Para que serve:** ordenar pedidos por risco de atraso no momento da compra, para priorizar acompanhamento,
  comunicação proativa com o cliente ou revisão da promessa em rotas problemáticas; estimar o prazo real de
  entrega, que a promessa da Olist superestima em cerca de 12 dias em média.
- **Para que não serve:** o score **não é uma probabilidade calibrada**. No teste, o decil de maior risco prevê
  87,6% e observa 7,8% de atraso. Não use o score como chance de atraso nem para recalcular a promessa ao cliente
  sem uma calibração própria. Não serve para avaliar vendedores individualmente nem para decisões automáticas
  sobre clientes.
- **Usuários:** times de operação logística e de atendimento, como apoio à decisão humana.

## Dados

- [Brazilian E-Commerce Public Dataset by Olist](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce),
  licença CC BY-NC-SA 4.0. Detalhes e anomalias conhecidas em [`dados.md`](dados.md).
- População: pedidos **entregues** com data de entrega em `marts.fct_deliveries`, compra entre 2017-01 e 2018-08.
- Divisão temporal: treino até 2018-03 (64.053 entregas, 8,0% de atraso), validação em 2018-04/05 (13.547;
  5,5%) e teste de 2018-06 a 2018-08 (18.603; 3,6%).

## Features

Só informações disponíveis no checkout, calculadas por `olist_platform.features` tanto no treino quanto na API:

- **Promessa e rota:** prazo prometido em dias, distância haversine entre os CEPs de vendedor e cliente, km por
  dia prometido, mesma UF, UF de origem e de destino.
- **Pedido:** valor dos itens, frete, frete ÷ valor, nº de itens e de vendedores, peso, volume, maior lado,
  categoria principal.
- **Calendário:** mês, dia da semana e hora da compra.
- **Histórico do vendedor**, só com entregas concluídas **antes** da compra: nº de entregas, taxa de atraso
  suavizada e prazo médio.

**Colunas excluídas por vazamento** (conhecidas só depois da compra):

| Coluna | Motivo |
|---|---|
| `approved_at` | Aprovação do pagamento: acontece depois da compra |
| `delivered_to_carrier_at`, `seller_handling_days` | Postagem pelo vendedor |
| `delivered_to_customer_at`, `delivery_date`, `carrier_transit_days` | Entrega: é o próprio alvo |
| `delivery_days`, `delay_days`, `is_late` | Alvos ou derivados diretos deles |
| `review_score` e demais campos de avaliação | O cliente avalia depois da entrega |
| `shipping_limit_at` (`fct_order_items`) | Calculado pela Olist a partir da aprovação, não da compra |
| `order_status` | Reflete o estado atual, não o da compra |

As features só podem sair de `RAW_INPUT_COLUMNS` (`src/olist_platform/features/build.py`); um teste unitário
falha se alguma coluna da tabela aparecer nas entradas ou nas features.

## Desempenho

O campeão e o limiar foram escolhidos só na validação; o teste foi olhado uma vez. Tabelas com todos os métodos
no README e em [`modelagem.md`](modelagem.md).

- **Classificador:** PR-AUC 0,153 na validação e 0,072 no teste, contra uma taxa base de 0,055 e 0,036. No
  teste, fica abaixo da regra da rota (0,121): é um trimestre de atraso baixo, depois do pico de 2018-02/03 que
  domina o fim do treino. Trocar o campeão olhando o teste seria selecionar no teste.
- **Regressor:** MAE de 4,36 dias no teste, contra 13,29 da promessa da Olist e 4,45 da mediana da rota.
- **Em produção simulada** (2018-04 a 2018-08, [`monitoramento.md`](monitoramento.md)): o lift caiu de 3,75
  para 1,55 e disparou um retreino em 2018-08, que o *quality gate* rejeitou (PR-AUC 0,078 do desafiante contra
  0,092 do campeão). A fração de pedidos sinalizados subiu de 26,4% para 84,2%: o limiar, escolhido num período
  de atraso alto, deixa de discriminar quando o atraso cai. Para uso real, ele precisaria ser reajustado com
  dados recentes ou definido pela capacidade de atendimento (por exemplo, os N pedidos de maior risco por dia).

## Limitações, riscos e vieses

- **Mudança de regime.** A taxa de atraso foi de 19,0% (2018-03) a 1,2% (2018-08) em poucos meses. Qualquer
  métrica vale para o regime em que foi medida.
- **Viés de sobrevivência.** Só entram pedidos entregues. Pedidos cancelados ficam de fora, e os muito atrasados
  do fim do período podem não ter sido entregues até a extração, o que subestima a taxa de atraso recente.
- **Desigualdade regional.** O atraso é muito mais comum em algumas UFs (AL 21,4%, MA 17,4%, SE 15,2%, contra
  4,5% em SP, em `analises.md`), e a UF do cliente é uma das features que mais pesam (SHAP). Sinalizar mais
  pedidos onde o serviço logístico é pior é esperado, mas usar o score para restringir a venda ou piorar a
  experiência nessas regiões reforçaria a desigualdade. Em 2018-08, o modelo sinalizou 94,7% dos pedidos do
  Nordeste, que teve 2,1% de atraso, contra 83,9% do Sudeste, com 7,2% de atraso (recortes em
  [`monitoramento.md`](monitoramento.md)).
- **Vendedores novos** não têm histórico e recebem a linha média da plataforma.
- **Snapshot do histórico.** A API usa o histórico do vendedor congelado no último treino. Entre dois treinos, ele
  envelhece, e as métricas offline (com histórico atualizado até a véspera) tendem a ser um pouco otimistas.
- **Calibração.** O score serve para ordenar pedidos. Probabilidades exigiriam calibrar o modelo na validação, o
  que fica como próximo passo.
- **Licença.** O modelo e o pacote exportado derivam de dados CC BY-NC-SA 4.0: qualquer uso precisa ser não
  comercial e citar a fonte.
