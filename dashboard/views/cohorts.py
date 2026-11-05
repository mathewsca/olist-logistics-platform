"""Monthly purchase cohorts: SLA over time and repurchase after a late first delivery."""

import streamlit as st

from olist_platform.analytics import charts, metrics
from olist_platform.analytics.formatting import format_number

deliveries = st.session_state["deliveries"]

st.title("Coortes")

st.subheader("Prazo real e nota por mês de compra")
monthly = metrics.monthly_sla(deliveries)
left, right = st.columns(2)
with left:
    st.altair_chart(
        charts.monthly_line(
            monthly, "median_delivery_days", value_title="Prazo real mediano (dias)"
        ),
        width="stretch",
    )
with right:
    st.altair_chart(
        charts.monthly_line(
            monthly, "avg_review_score", value_title="Nota média (1–5)", value_format=".2f"
        ),
        width="stretch",
    )

st.subheader("Recompra em 180 dias conforme a primeira entrega")
st.caption(
    "Clientes agrupados pelo mês da primeira compra entregue. Recompra = outro pedido "
    "(não cancelado) em até 180 dias. Só entram primeiras compras com 180 dias de janela "
    "observada, e o histórico inteiro é usado para as recompras, mesmo fora do filtro de período."
)
# Later orders must count even outside the period filter, so the filter applies to the first order.
outcomes = st.session_state["first_delivery_outcomes"]
outcomes = outcomes[outcomes["first_order_id"].isin(deliveries["order_id"])]
if outcomes.empty:
    st.info("Nenhuma primeira compra no filtro tem 180 dias de janela observada.")
    st.stop()

overall = metrics.repurchase_rate(outcomes, ["first_delivery_late"]).assign(
    group=lambda frame: charts.group_label(frame["first_delivery_late"])
)
columns = st.columns(len(overall))
for column, row in zip(columns, overall.itertuples(), strict=True):
    column.metric(
        f"Recompra, 1ª entrega {row.group.lower()}",
        f"{format_number(row.repurchase_pct, 2)}%",
        help=f"{format_number(row.customers)} clientes",
    )

by_cohort = metrics.repurchase_rate(outcomes, ["cohort_month", "first_delivery_late"]).assign(
    group=lambda frame: charts.group_label(frame["first_delivery_late"])
)
st.altair_chart(
    charts.grouped_monthly_lines(
        by_cohort,
        "repurchase_pct",
        "group",
        value_title="% que recomprou em 180 dias",
        group_title="Primeira entrega",
    ),
    width="stretch",
)
st.caption("Coortes pequenas oscilam muito: confira o número de clientes no tooltip ou na tabela.")

with st.expander("Tabelas"):
    st.dataframe(monthly, hide_index=True, width="stretch")
    st.dataframe(by_cohort.drop(columns="first_delivery_late"), hide_index=True, width="stretch")
