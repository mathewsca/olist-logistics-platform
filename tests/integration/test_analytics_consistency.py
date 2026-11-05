"""The dashboard (pandas) and docs/analises.md (dbt analyses) must show the same numbers."""

import re

import psycopg
import pytest

from olist_platform.analytics import metrics
from olist_platform.analytics.datasets import load_from_postgres
from olist_platform.analytics.report import compiled_analyses_dir, run_analyses
from olist_platform.ingestion.settings import WarehouseSettings, load_dotenv_if_present
from olist_platform.transform.dbt import project_dir, run_dbt

pytestmark = pytest.mark.integration

# SQL rounds to 1-2 decimals; half a unit of the last decimal plus float noise.
TOLERANCE = 0.051


@pytest.fixture(scope="module")
def sources():
    load_dotenv_if_present()
    conninfo = WarehouseSettings.from_env().conninfo()
    try:
        conn = psycopg.connect(conninfo)
    except psycopg.OperationalError as error:
        pytest.fail(f"Warehouse not reachable (did you run `make up`?): {error}")
    with conn:
        if conn.execute("select to_regclass('marts.fct_deliveries')").fetchone()[0] is None:
            pytest.fail("marts.fct_deliveries not found: run `make dbt-build` first")
        run_dbt(["compile", "--select", "path:analyses"])
        results = run_analyses(conn, compiled_analyses_dir(project_dir()))
    sql = {result.analysis.name: result for result in results}
    return sql, load_from_postgres(conninfo)


def sql_rows(sources, name: str) -> dict[str, dict[str, float]]:
    """Rows of one analysis keyed by their first column, without the "1. " ordering prefix."""
    result = sources[0][name]
    return {
        re.sub(r"^\d+\. ", "", str(row[0])): dict(zip(result.columns[1:], row[1:], strict=True))
        for row in result.rows
    }


def assert_same(sql: dict[str, dict], frame, key: str, columns: list[str]) -> None:
    pandas_rows = frame.assign(**{key: frame[key].astype(str)}).set_index(key)
    assert set(sql) == set(pandas_rows.index)
    for label, values in sql.items():
        for column in columns:
            expected, actual = values[column], pandas_rows.loc[label, column]
            if expected is None:
                assert actual != actual, (label, column)  # NaN
            else:
                assert float(actual) == pytest.approx(float(expected), abs=TOLERANCE), (
                    label,
                    column,
                )


def test_monthly_late_rate(sources):
    frame = metrics.monthly_sla(sources[1]["deliveries"])
    columns = ["deliveries", "late_pct", "avg_days_late_when_late", "median_delivery_days"]
    assert_same(sql_rows(sources, "monthly_late_rate"), frame, "year_month", columns)


def test_freight_and_distance_bands(sources):
    deliveries = sources[1]["deliveries"]
    assert_same(
        sql_rows(sources, "late_rate_by_freight"),
        metrics.late_rate_by_freight(deliveries),
        "freight_band",
        ["deliveries", "late_pct"],
    )
    assert_same(
        sql_rows(sources, "late_rate_by_distance"),
        metrics.late_rate_by_distance(deliveries),
        "distance_band",
        ["deliveries", "late_pct"],
    )


def test_review_by_delay(sources):
    assert_same(
        sql_rows(sources, "late_vs_review"),
        metrics.review_by_delay(sources[1]["deliveries"]),
        "delay_band",
        ["reviewed_deliveries", "avg_review_score", "low_score_pct"],
    )


def test_promise_slack_by_state(sources):
    sql = sql_rows(sources, "estimate_bias")
    overall = sql.pop("all")
    assert_same(
        sql,
        metrics.slack_by_state(sources[1]["deliveries"]),
        "destination_state",
        ["deliveries", "median_slack_days", "early_7_plus_pct", "late_pct"],
    )
    summary = metrics.sla_summary(sources[1]["deliveries"])
    assert summary.deliveries == overall["deliveries"]


def test_repurchase_after_first_delivery(sources):
    outcomes = metrics.first_delivery_outcomes(sources[1]["deliveries"], sources[1]["orders"])
    frame = metrics.repurchase_rate(outcomes, ["first_delivery_late"]).assign(
        first_delivery=lambda f: f["first_delivery_late"].map({True: "late", False: "on time"})
    )
    sql = {
        label: {"customers": v["customers"], "repurchase_pct": v["repurchase_180d_pct"]}
        for label, v in sql_rows(sources, "repurchase_after_first_delivery").items()
    }
    assert_same(sql, frame, "first_delivery", ["customers", "repurchase_pct"])


def test_monthly_revenue(sources):
    sql = sql_rows(sources, "monthly_revenue")
    frame = metrics.monthly_revenue(sources[1]["deliveries"])
    columns = ["deliveries", "avg_ticket_brl", "freight_share_pct", "late_revenue_pct"]
    assert_same(sql, frame, "year_month", columns)
    # Revenue is rounded to whole reais in SQL.
    revenue = frame.set_index("year_month")["revenue_brl"]
    for month, values in sql.items():
        assert revenue[month] == pytest.approx(float(values["revenue_brl"]), abs=0.51)


def test_weekday_freight_and_payments(sources):
    deliveries = sources[1]["deliveries"]
    weekday = metrics.late_rate_by_weekday(deliveries)
    # sql_rows drops the "1. " ordering prefix; the pandas labels keep it.
    weekday["purchase_weekday"] = weekday["purchase_weekday"].str.split(". ").str[1]
    assert_same(
        sql_rows(sources, "late_rate_by_purchase_weekday"),
        weekday,
        "purchase_weekday",
        ["deliveries", "late_pct", "avg_seller_handling_days", "avg_delivery_days"],
    )
    assert_same(
        sql_rows(sources, "freight_share_by_distance"),
        metrics.freight_share_by_distance(deliveries),
        "distance_band",
        ["deliveries", "avg_freight_value", "median_freight_share_pct"],
    )
    assert_same(
        sql_rows(sources, "late_rate_by_payment_type"),
        metrics.late_rate_by_payment_type(deliveries),
        "payment_type",
        ["deliveries", "median_approval_hours", "avg_delivery_days", "late_pct"],
    )


def test_review_comments_and_sellers(sources):
    deliveries = sources[1]["deliveries"]
    assert_same(
        sql_rows(sources, "review_comments_by_score"),
        metrics.review_comments_by_score(deliveries),
        "score_group",
        ["comments", "mentions_delivery_pct", "late_pct"],
    )
    assert_same(
        sql_rows(sources, "seller_late_vs_review"),
        metrics.seller_late_vs_review(deliveries),
        "seller_late_band",
        ["sellers", "deliveries", "avg_review_score"],
    )


def test_every_known_issue_has_its_audit_table(sources):
    quality = sources[1]["data_quality"]
    assert not quality.empty
    assert quality["violations"].notna().all(), quality.loc[quality["violations"].isna()]
