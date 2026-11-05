"""Streamlit entry point: loads the marts once, applies the sidebar filters and routes to the pages.

Run with ``make dashboard`` (``streamlit run dashboard/app.py``).
"""

import pandas as pd
import streamlit as st

from olist_platform.analytics.datasets import load_datasets
from olist_platform.analytics.formatting import format_number
from olist_platform.analytics.metrics import first_delivery_outcomes, with_year_month
from olist_platform.ingestion.settings import load_dotenv_if_present

# 2016 and Sep-Oct 2018 have a handful of orders each (docs/dados.md), which only adds noise.
DEFAULT_PERIOD = ("2017-01", "2018-08")
ALL_REGIONS = ("Norte", "Nordeste", "Centro-Oeste", "Sudeste", "Sul")
UNFILTERED_PAGES = ("quality", "monitoring")


# cache_resource shares one copy across reruns (cache_data would unpickle ~20 MB per interaction);
# pages only read these frames, every metric returns new ones.
@st.cache_resource(ttl=3600, show_spinner="Carregando os marts...")
def cached_datasets() -> dict[str, pd.DataFrame]:
    """Datasets from the configured source, plus the per-customer repurchase outcomes."""
    load_dotenv_if_present()
    datasets = load_datasets()
    datasets["deliveries"] = with_year_month(datasets["deliveries"])
    # Repurchase needs the full history, so it is computed once, before any filter.
    datasets["first_delivery_outcomes"] = first_delivery_outcomes(
        datasets["deliveries"], datasets["orders"]
    )
    return datasets


def sidebar_filters(deliveries: pd.DataFrame) -> pd.DataFrame:
    """Purchase period and customer region chosen in the sidebar."""
    months = sorted(deliveries["year_month"].unique())
    if not months:
        return deliveries
    default_start = next((m for m in months if m >= DEFAULT_PERIOD[0]), months[0])
    default_end = next((m for m in reversed(months) if m <= DEFAULT_PERIOD[1]), months[-1])
    start, end = st.sidebar.select_slider(
        "Mês de compra", options=months, value=(default_start, default_end), key="period"
    )
    regions = st.sidebar.multiselect(
        "Região do cliente", options=ALL_REGIONS, default=ALL_REGIONS, key="regions"
    )
    selected = deliveries["year_month"].between(start, end) & deliveries["destination_region"].isin(
        regions
    )
    st.sidebar.caption(f"{format_number(selected.sum())} entregas no filtro")
    return deliveries[selected]


def main() -> None:
    """Build the navigation and run the selected page."""
    st.set_page_config(page_title="Olist · SLA de entregas", page_icon=":truck:", layout="wide")
    datasets = cached_datasets()
    st.session_state["deliveries"] = sidebar_filters(datasets["deliveries"])
    st.session_state["first_delivery_outcomes"] = datasets["first_delivery_outcomes"]
    st.session_state["state_centroids"] = datasets["state_centroids"]
    st.session_state["monitoring_runs"] = datasets.get("monitoring_runs", pd.DataFrame())
    st.session_state["data_quality"] = datasets.get("data_quality", pd.DataFrame())
    st.sidebar.caption(
        "Fonte: Brazilian E-Commerce Public Dataset by Olist (CC BY-NC-SA 4.0), "
        "pedidos entregues com data de entrega."
    )

    pages = [
        st.Page("views/sla_overview.py", title="Visão geral de SLA", default=True),
        st.Page("views/demand.py", title="Demanda e receita"),
        st.Page("views/routes.py", title="Rotas e vendedores"),
        st.Page("views/categories.py", title="Categorias, frete e distância"),
        st.Page("views/delay_vs_review.py", title="Atraso × Avaliação"),
        st.Page("views/cohorts.py", title="Coortes"),
        st.Page("views/quality.py", title="Qualidade dos dados"),
        st.Page("views/monitoring.py", title="Monitoramento do modelo"),
    ]
    navigation = st.navigation(pages)
    # These pages ignore the sidebar filters, so an empty filter must not hide them.
    if st.session_state["deliveries"].empty and navigation.url_path not in UNFILTERED_PAGES:
        st.warning("Nenhuma entrega no filtro: amplie o período ou selecione ao menos uma região.")
        return
    navigation.run()


main()
