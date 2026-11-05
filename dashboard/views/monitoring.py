"""Production replay of the late-delivery model: monthly performance, drift and retraining."""

import pandas as pd
import streamlit as st

from olist_platform.analytics import charts
from olist_platform.analytics.formatting import format_number
from olist_platform.monitoring.performance import LIFT_DROP_TRIGGER

runs = st.session_state["monitoring_runs"]

st.title("Monitoramento do modelo")
st.caption(
    "Simulação de produção de 2018-04 a 2018-08: cada mês é avaliado pelo campeão que estava no "
    "ar quando ele começou, um mês depois de fechar. Os filtros do menu lateral não se aplicam."
)

if runs.empty:
    st.info(
        "Nenhum mês monitorado ainda: rode `make monitor` (ou a DAG `olist_monitoring_retrain`)."
    )
    st.stop()

monthly = runs.assign(
    year_month=pd.to_datetime(runs["month"]).dt.strftime("%Y-%m"),
    drift_pct=runs["drift_share"] * 100,
)
retrained = runs["retrain_reasons"].notna()
promoted = runs["gate_passed"].fillna(False).astype(bool)
latest = runs.iloc[-1]

headline = {
    "Meses monitorados": format_number(len(runs)),
    "Retreinos disparados": format_number(int(retrained.sum())),
    "Desafiantes promovidos": format_number(int(promoted.sum())),
    "Lift no último mês": format_number(latest["lift"], 2),
}
for column, (label, value) in zip(st.columns(len(headline)), headline.items(), strict=True):
    column.metric(label, value)

st.subheader("Lift do classificador (PR-AUC ÷ taxa de atraso)")
st.caption(
    f"1 = aleatório. O gatilho de retreino é cair abaixo de {1 - LIFT_DROP_TRIGGER:.0%} do lift "
    "da validação."
)
st.altair_chart(
    charts.monthly_line(monthly, "lift", value_title="Lift", value_format=".2f"), width="stretch"
)
st.subheader("Features com drift (Evidently)")
st.altair_chart(
    charts.monthly_line(monthly, "drift_pct", value_title="% das features"), width="stretch"
)

st.subheader("Decisões")
decisions = pd.DataFrame(
    {
        "Mês": monthly["year_month"],
        "Campeão": "v" + runs["champion_version"].astype(str),
        "Motivo do retreino": runs["retrain_reasons"].fillna("-"),
        "Desafiante": runs["challenger_version"].map(lambda v: "-" if pd.isna(v) else f"v{v}"),
        "Gate": runs["gate_passed"].map(
            lambda passed: "-" if pd.isna(passed) else ("promovido" if passed else "rejeitado")
        ),
        "Detalhe": runs["gate_detail"].fillna("-"),
    }
)
st.dataframe(decisions, hide_index=True, width="stretch")
