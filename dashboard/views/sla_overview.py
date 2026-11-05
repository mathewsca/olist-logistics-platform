"""SLA overview: headline numbers and the monthly late rate."""

import streamlit as st

from olist_platform.analytics import charts, metrics
from olist_platform.analytics.formatting import format_number

deliveries = st.session_state["deliveries"]
summary = metrics.sla_summary(deliveries)
monthly = metrics.monthly_sla(deliveries)

st.title("Visão geral de SLA")
st.caption(
    "Atraso = entregue depois da data prometida pela Olist na compra (datas de calendário). "
    "Período e região no menu lateral."
)

headline = {
    "Entregas": format_number(summary.deliveries),
    "Com atraso": f"{format_number(summary.late_pct, 1)}%",
    "Prazo real (mediana)": f"{format_number(summary.median_delivery_days, 1)} dias",
    "Prazo prometido (média)": f"{format_number(summary.avg_promised_days, 1)} dias",
    "Nota média": format_number(summary.avg_review_score, 2),
}
for column, (label, value) in zip(st.columns(len(headline)), headline.items(), strict=True):
    column.metric(label, value)

st.subheader("Entregas com atraso por mês de compra")
st.altair_chart(
    charts.monthly_line(monthly, "late_pct", value_title="% com atraso"), width="stretch"
)
st.subheader("Entregas por mês de compra")
st.altair_chart(
    charts.monthly_columns(monthly, "deliveries", value_title="Entregas"), width="stretch"
)

with st.expander("Tabela mensal"):
    st.dataframe(monthly, hide_index=True, width="stretch")
