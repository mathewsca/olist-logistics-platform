"""Seller state -> customer state routes, and how each seller's lateness relates to its score."""

import pydeck as pdk
import streamlit as st

from olist_platform.analytics import charts, metrics

deliveries = st.session_state["deliveries"]

st.title("Rotas e vendedores")
st.caption(
    "Origem = UF do vendedor do item mais caro; destino = UF do cliente. Arcos ligam os "
    "centroides das UFs: a espessura é o volume e o tom de azul, a taxa de atraso (mais escuro "
    "= mais atraso)."
)

min_deliveries = st.slider("Mínimo de entregas por rota", 10, 1000, 100, step=10)
routes = metrics.route_summary(deliveries, min_deliveries)
if routes.empty:
    st.info("Nenhuma rota com esse volume no filtro.")
    st.stop()

arcs = charts.route_arcs(routes, st.session_state["state_centroids"])
layer = pdk.Layer(
    "ArcLayer",
    data=arcs,
    get_source_position=["origin_lng", "origin_lat"],
    get_target_position=["destination_lng", "destination_lat"],
    get_source_color="color",
    get_target_color="color",
    get_width="width",
    pickable=True,
    auto_highlight=True,
)
st.pydeck_chart(
    pdk.Deck(
        layers=[layer],
        initial_view_state=pdk.ViewState(latitude=-15, longitude=-52, zoom=3.2, pitch=35),
        map_provider="carto",
        map_style=pdk.map_styles.CARTO_LIGHT,
        tooltip={
            "text": "{origin_state} → {destination_state}\n{deliveries} entregas\n"
            "{late_pct_label} com atraso"
        },
    )
)

left, right = st.columns(2)
with left:
    st.subheader("Rotas com maior taxa de atraso")
    worst = routes.nlargest(15, "late_pct").assign(
        route=lambda frame: frame["origin_state"] + " → " + frame["destination_state"]
    )
    st.altair_chart(
        charts.horizontal_bars(
            worst,
            "route",
            "late_pct",
            category_title="Rota",
            value_title="% com atraso",
            tooltip_extra=("deliveries",),
        ),
        width="stretch",
    )
with right:
    st.subheader("Atraso por UF do cliente")
    by_state = metrics.late_rate_by(deliveries, "destination_state")
    st.altair_chart(
        charts.horizontal_bars(
            by_state,
            "destination_state",
            "late_pct",
            category_title="UF do cliente",
            value_title="% com atraso",
            tooltip_extra=("deliveries",),
        ),
        width="stretch",
    )

with st.expander("Tabela de rotas"):
    st.dataframe(routes, hide_index=True, width="stretch")

st.subheader("Vendedores: taxa de atraso × nota média")
st.caption(
    f"Um ponto por vendedor com pelo menos {metrics.MIN_SELLER_DELIVERIES} entregas no filtro; "
    "a área é o volume."
)
sellers = metrics.seller_summary(deliveries, metrics.MIN_SELLER_DELIVERIES)
if sellers.empty:
    st.info("Nenhum vendedor com esse volume no filtro.")
else:
    st.altair_chart(
        charts.scatter(
            sellers,
            "late_pct",
            "avg_review_score",
            "deliveries",
            x_title="% com atraso",
            y_title="Nota média",
            size_title="Entregas",
            tooltip_extra=("seller_id",),
        ),
        width="stretch",
    )
    with st.expander("Vendedores por faixa de atraso"):
        st.dataframe(metrics.seller_late_vs_review(deliveries), hide_index=True, width="stretch")
