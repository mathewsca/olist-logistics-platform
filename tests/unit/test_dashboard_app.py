from pathlib import Path

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from olist_platform.analytics.datasets import export_parquet
from tests.analytics_data import (
    centroids_frame,
    data_quality_frame,
    deliveries_frame,
    monitoring_runs_frame,
    orders_frame,
)

APP = str(Path(__file__).parents[2] / "dashboard" / "app.py")
PAGES = [
    "views/sla_overview.py",
    "views/demand.py",
    "views/routes.py",
    "views/categories.py",
    "views/delay_vs_review.py",
    "views/cohorts.py",
    "views/quality.py",
    "views/monitoring.py",
]


@pytest.fixture(autouse=True)
def parquet_source(tmp_path, monkeypatch):
    """Points the app at a tiny Parquet extract, so the tests need no database."""
    export_parquet(
        {
            "deliveries": deliveries_frame(),
            "orders": orders_frame(),
            "state_centroids": centroids_frame(),
        },
        tmp_path,
    )
    monkeypatch.setenv("DASHBOARD_SOURCE", "parquet")
    monkeypatch.setenv("DASHBOARD_PARQUET_LOCATION", str(tmp_path))
    # The app caches the datasets per process; each test must read its own extract.
    st.cache_resource.clear()


def run_page(page: str) -> AppTest:
    app = AppTest.from_file(APP, default_timeout=60)
    app.run()
    if page != PAGES[0]:
        app.switch_page(page).run()
    return app


@pytest.mark.parametrize("page", PAGES)
def test_every_page_renders_without_errors(page):
    app = run_page(page)

    assert not app.exception
    assert app.title


def test_overview_shows_the_headline_numbers():
    app = run_page(PAGES[0])

    metrics = {metric.label: metric.value for metric in app.metric}
    assert metrics["Entregas"] == "6"
    assert metrics["Com atraso"] == "33,3%"


def test_empty_region_filter_shows_a_warning_instead_of_a_page():
    app = run_page(PAGES[0])
    app.multiselect(key="regions").set_value([]).run()

    assert not app.exception
    assert app.warning
    assert not app.title


def test_monitoring_page_asks_for_the_simulation_when_there_is_none():
    app = run_page("views/monitoring.py")

    assert not app.exception
    assert "make monitor" in app.info[0].value


def test_monitoring_page_shows_the_decisions(tmp_path):
    export_parquet({"monitoring_runs": monitoring_runs_frame()}, tmp_path)
    app = run_page("views/monitoring.py")

    assert not app.exception
    metrics = {metric.label: metric.value for metric in app.metric}
    assert metrics["Retreinos disparados"] == "1"
    assert metrics["Desafiantes promovidos"] == "0"
    assert list(app.dataframe[0].value["Gate"]) == ["-", "rejeitado"]


def test_monitoring_page_ignores_an_empty_region_filter():
    app = run_page("views/monitoring.py")
    app.multiselect(key="regions").set_value([]).run()

    assert not app.exception
    assert not app.warning
    assert app.title[0].value == "Monitoramento do modelo"


def test_quality_page_asks_for_the_build_when_there_are_no_results():
    app = run_page("views/quality.py")

    assert not app.exception
    assert "make dbt-build" in app.info[0].value


def test_quality_page_counts_the_issues_with_violations(tmp_path):
    export_parquet({"data_quality": data_quality_frame()}, tmp_path)
    app = run_page("views/quality.py")

    assert not app.exception
    metrics = {metric.label: metric.value for metric in app.metric}
    assert metrics["Problemas monitorados"] == "2"
    assert metrics["Com violações"] == "1"
    assert metrics["Linhas afetadas"] == "12"


def test_quality_page_ignores_an_empty_region_filter():
    app = run_page("views/quality.py")
    app.multiselect(key="regions").set_value([]).run()

    assert not app.exception
    assert app.title[0].value == "Qualidade dos dados"
