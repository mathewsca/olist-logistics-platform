"""Known issues of the source data, how many rows each affects and what the pipeline does."""

import streamlit as st

from olist_platform.analytics.formatting import format_number

quality = st.session_state["data_quality"]

st.title("Qualidade dos dados")
st.caption(
    "Cada problema tem um teste dbt com severidade warn, que conta as violações a cada "
    "`dbt build` e guarda as linhas no schema audit. Os filtros do menu lateral não se aplicam."
)

if quality.empty:
    st.info("Nenhum resultado de qualidade ainda: rode `make dbt-build`.")
    st.stop()

found = quality["violations"].fillna(0)
headline = {
    "Problemas monitorados": format_number(len(quality)),
    "Com violações": format_number(int((found > 0).sum())),
    "Linhas afetadas": format_number(int(found.sum())),
}
for column, (label, value) in zip(st.columns(len(headline)), headline.items(), strict=True):
    column.metric(label, value)

st.dataframe(
    quality.rename(
        columns={
            "issue": "Problema",
            "model": "Modelo",
            "violations": "Violações",
            "treatment": "Tratamento",
            "test_name": "Teste dbt",
        }
    )[["Problema", "Violações", "Tratamento", "Modelo", "Teste dbt"]],
    hide_index=True,
    width="stretch",
)
