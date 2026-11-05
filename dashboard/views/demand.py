"""Demand and revenue seen from the operation: when orders arrive, what lateness puts at risk."""

import streamlit as st

from olist_platform.analytics import charts, metrics
from olist_platform.analytics.formatting import format_number

deliveries = st.session_state["deliveries"]

st.title("Demanda e receita")
st.caption(
    "Receita = itens + frete dos pedidos entregues. Período e região no menu lateral; a data é "
    "a da compra."
)

revenue = metrics.revenue(deliveries)
total = revenue.sum()
late_share = revenue[deliveries["is_late"]].sum() / total * 100
freight_share = deliveries["freight_value"].sum() / total * 100
headline = {
    "Receita entregue": f"R$ {format_number(total / 1e6, 2)} mi",
    "Ticket médio": f"R$ {format_number(revenue.mean(), 2)}",
    "Receita com atraso": f"{format_number(late_share, 1)}%",
    "Frete na receita": f"{format_number(freight_share, 1)}%",
}
for column, (label, value) in zip(st.columns(len(headline)), headline.items(), strict=True):
    column.metric(label, value)

monthly = metrics.monthly_revenue(deliveries)
st.subheader("Receita entregue por mês de compra")
st.altair_chart(
    charts.monthly_columns(monthly.round({"revenue_brl": 0}), "revenue_brl", value_title="R$"),
    width="stretch",
)
st.subheader("% da receita entregue com atraso")
st.altair_chart(
    charts.monthly_line(monthly, "late_revenue_pct", value_title="% da receita"), width="stretch"
)

st.subheader("Quando os pedidos chegam")
st.caption("Entregas por dia da semana e hora da compra: os picos pressionam a expedição.")
st.altair_chart(
    charts.heatmap(
        metrics.weekday_hour_volume(deliveries),
        "purchase_hour",
        "purchase_weekday",
        "deliveries",
        x_title="Hora da compra",
        y_title="Dia da semana",
        value_title="Entregas",
    ),
    width="stretch",
)

weekday = metrics.late_rate_by_weekday(deliveries)
freight = metrics.freight_share_by_distance(deliveries)
payments = metrics.late_rate_by_payment_type(deliveries)
left, right = st.columns(2)
with left:
    st.subheader("Peso do frete por distância")
    st.altair_chart(
        charts.horizontal_bars(
            freight,
            "distance_band",
            "median_freight_share_pct",
            category_title="Distância (km)",
            value_title="Frete ÷ valor dos itens (mediana, %)",
            sort_by_value=False,
            tooltip_extra=("deliveries",),
        ),
        width="stretch",
    )
with right:
    st.subheader("Horas até a aprovação do pagamento")
    st.altair_chart(
        charts.horizontal_bars(
            payments,
            "payment_type",
            "median_approval_hours",
            category_title="Forma de pagamento",
            value_title="Horas (mediana)",
            tooltip_extra=("deliveries", "late_pct"),
        ),
        width="stretch",
    )

with st.expander("Tabelas"):
    st.dataframe(monthly, hide_index=True, width="stretch")
    st.dataframe(weekday, hide_index=True, width="stretch")
    st.dataframe(freight, hide_index=True, width="stretch")
    st.dataframe(payments, hide_index=True, width="stretch")
