"""How lateness relates to the review score."""

import streamlit as st

from olist_platform.analytics import charts, metrics
from olist_platform.analytics.formatting import format_number

deliveries = st.session_state["deliveries"]

st.title("Atraso × Avaliação")
st.caption(
    "Avaliação mais recente do pedido, entre as entregas avaliadas. Atraso = dias entre a data "
    "prometida e a entrega (negativo = adiantado)."
)

reviewed = deliveries[deliveries["review_score"].notna()]
on_time = reviewed.loc[~reviewed["is_late"], "review_score"]
late = reviewed.loc[reviewed["is_late"], "review_score"]
headline = {
    "Nota média no prazo": format_number(on_time.mean(), 2) if len(on_time) else "-",
    "Nota média com atraso": format_number(late.mean(), 2) if len(late) else "-",
    "Notas 1–2 no prazo": f"{format_number(metrics.pct(on_time <= 2), 1)}%"
    if len(on_time)
    else "-",
    "Notas 1–2 com atraso": f"{format_number(metrics.pct(late <= 2), 1)}%" if len(late) else "-",
}
for column, (label, value) in zip(st.columns(len(headline)), headline.items(), strict=True):
    column.metric(label, value)

curve = metrics.review_by_delay(deliveries)
left, right = st.columns(2)
with left:
    st.subheader("Nota média por faixa de atraso")
    st.altair_chart(
        charts.horizontal_bars(
            curve,
            "delay_band",
            "avg_review_score",
            category_title="Faixa de atraso",
            value_title="Nota média (1–5)",
            sort_by_value=False,
            value_format=".2f",
            tooltip_extra=("reviewed_deliveries",),
        ),
        width="stretch",
    )
with right:
    st.subheader("% de notas 1–2 por faixa de atraso")
    st.altair_chart(
        charts.horizontal_bars(
            curve,
            "delay_band",
            "low_score_pct",
            category_title="Faixa de atraso",
            value_title="% de notas 1–2",
            sort_by_value=False,
            tooltip_extra=("reviewed_deliveries",),
        ),
        width="stretch",
    )

with st.expander("Tabela"):
    st.dataframe(curve, hide_index=True, width="stretch")

st.subheader("O que dizem os comentários")
st.caption(
    "Avaliações com comentário escrito. Menciona entrega = o texto cita entrega, prazo, atraso, "
    "recebimento, correios ou transportadora."
)
comments = metrics.review_comments_by_score(deliveries)
if comments.empty:
    st.info("Nenhuma avaliação com comentário no filtro.")
else:
    st.altair_chart(
        charts.horizontal_bars(
            comments,
            "score_group",
            "mentions_delivery_pct",
            category_title="Nota",
            value_title="% dos comentários que mencionam a entrega",
            sort_by_value=False,
            tooltip_extra=("comments", "late_pct"),
        ),
        width="stretch",
    )
    with st.expander("Tabela dos comentários"):
        st.dataframe(comments, hide_index=True, width="stretch")
