"""Late rate by product category, freight band and distance band."""

import streamlit as st

from olist_platform.analytics import charts, metrics

deliveries = st.session_state["deliveries"]

st.title("Categorias, frete e distância")
st.caption(
    "Categoria do item mais caro do pedido. Frete e distância andam juntos (frete maior = rota "
    "mais longa), então as duas faixas não são efeitos independentes."
)

min_deliveries = st.slider("Mínimo de entregas por categoria", 100, 3000, 1000, step=100)
categories = metrics.late_rate_by_category(deliveries, min_deliveries)
st.subheader("Atraso por categoria")
if categories.empty:
    st.info("Nenhuma categoria com esse volume no filtro.")
else:
    st.altair_chart(
        charts.horizontal_bars(
            categories,
            "product_category",
            "late_pct",
            category_title="Categoria",
            value_title="% com atraso",
            tooltip_extra=("deliveries",),
        ),
        width="stretch",
    )

freight = metrics.late_rate_by_freight(deliveries)
distance = metrics.late_rate_by_distance(deliveries)
left, right = st.columns(2)
with left:
    st.subheader("Atraso por faixa de frete (R$)")
    st.altair_chart(
        charts.horizontal_bars(
            freight,
            "freight_band",
            "late_pct",
            category_title="Frete (R$)",
            value_title="% com atraso",
            sort_by_value=False,
            tooltip_extra=("deliveries",),
        ),
        width="stretch",
    )
with right:
    st.subheader("Atraso por faixa de distância (km)")
    st.altair_chart(
        charts.horizontal_bars(
            distance,
            "distance_band",
            "late_pct",
            category_title="Distância (km)",
            value_title="% com atraso",
            sort_by_value=False,
            tooltip_extra=("deliveries",),
        ),
        width="stretch",
    )

with st.expander("Tabelas"):
    st.dataframe(categories, hide_index=True, width="stretch")
    st.dataframe(freight, hide_index=True, width="stretch")
    st.dataframe(distance, hide_index=True, width="stretch")
