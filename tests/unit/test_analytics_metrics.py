import pandas as pd
import pytest

from olist_platform.analytics import metrics
from tests.analytics_data import deliveries_frame, orders_frame


@pytest.fixture
def deliveries() -> pd.DataFrame:
    return deliveries_frame()


def test_sla_summary_ignores_missing_reviews(deliveries):
    summary = metrics.sla_summary(deliveries)

    assert summary.deliveries == 6
    assert summary.late_pct == pytest.approx(100 / 3)
    assert summary.median_delivery_days == pytest.approx(10.5)
    assert summary.avg_review_score == pytest.approx(17 / 5)


def test_monthly_sla_averages_lateness_only_over_late_orders(deliveries):
    monthly = metrics.monthly_sla(deliveries).set_index("year_month")

    assert list(monthly.index) == ["2017-01", "2017-02", "2017-03", "2017-08"]
    assert monthly.loc["2017-01", "deliveries"] == 2
    assert monthly.loc["2017-01", "late_pct"] == pytest.approx(50)
    assert monthly.loc["2017-01", "avg_days_late_when_late"] == pytest.approx(10)
    assert monthly.loc["2017-01", "median_delivery_days"] == pytest.approx(17.5)
    assert pd.isna(monthly.loc["2017-03", "avg_days_late_when_late"])


def test_freight_bands_include_the_lower_bound(deliveries):
    banded = metrics.band(deliveries["freight_value"], metrics.FREIGHT_BANDS, right=False)

    assert list(banded) == ["< 10", "15-20", "10-15", ">= 50", "30-50", "20-30"]


def test_distance_bands_put_missing_distance_in_unknown(deliveries):
    result = metrics.late_rate_by_distance(deliveries).set_index("distance_band")

    assert result.loc["300-600", "deliveries"] == 2
    assert result.loc["unknown", "late_pct"] == pytest.approx(100)
    assert list(result.index) == ["< 100", "300-600", ">= 2000", "unknown"]


def test_delay_bands_treat_the_promised_day_as_its_own_band():
    delays = pd.Series([-15, -14, -1, 0, 1, 3, 4, 15])
    banded = metrics.band(delays, metrics.DELAY_BANDS, right=True)

    assert list(banded) == [
        "15+ days early",
        "8-14 days early",
        "1-7 days early",
        "on the promised day",
        "1-3 days late",
        "1-3 days late",
        "4-7 days late",
        "15+ days late",
    ]


def test_review_by_delay_uses_only_reviewed_deliveries(deliveries):
    result = metrics.review_by_delay(deliveries).set_index("delay_band")

    assert result["reviewed_deliveries"].sum() == 5
    assert result.loc["15+ days early", "avg_review_score"] == pytest.approx(4.5)
    assert result.loc["1-3 days late", "low_score_pct"] == pytest.approx(100)
    assert "on the promised day" not in result.index


def test_categories_below_the_minimum_are_dropped_and_missing_is_unknown(deliveries):
    result = metrics.late_rate_by_category(deliveries, min_deliveries=1)

    assert list(result["product_category"]) == ["auto", "toys", "unknown"]
    assert list(metrics.late_rate_by_category(deliveries, 3)["product_category"]) == ["toys"]


def test_route_summary_keeps_busy_routes_busiest_first(deliveries):
    routes = metrics.route_summary(deliveries, min_deliveries=2)

    assert list(zip(routes["origin_state"], routes["destination_state"], strict=True)) == [
        ("SP", "SP"),
        ("SP", "RJ"),
    ]
    assert routes.loc[1, "late_pct"] == pytest.approx(50)


def test_slack_by_state_is_promised_minus_actual_days(deliveries):
    result = metrics.slack_by_state(deliveries).set_index("destination_state")

    assert result.loc["SP", "median_slack_days"] == pytest.approx(11)
    assert result.loc["SP", "early_7_plus_pct"] == pytest.approx(200 / 3)
    assert list(result.index) == ["SP", "RJ", "BA"]


def test_first_delivery_outcomes_need_a_full_window_and_skip_canceled_orders(deliveries):
    outcomes = metrics.first_delivery_outcomes(deliveries, orders_frame()).set_index(
        "customer_unique_id"
    )

    # u5 bought too close to the last purchase to have 180 days of history.
    assert sorted(outcomes.index) == ["u1", "u2", "u3", "u4"]
    assert outcomes.loc["u1", "repurchased"]
    assert outcomes.loc["u2", "repurchased"]
    assert not outcomes.loc["u3", "repurchased"]
    assert outcomes.loc["u2", "first_delivery_late"]
    assert outcomes.loc["u1", "first_order_id"] == "o1"


def test_repurchase_window_excludes_orders_after_it(deliveries):
    outcomes = metrics.first_delivery_outcomes(
        deliveries, orders_frame(), window=pd.Timedelta(days=30)
    ).set_index("customer_unique_id")

    # u1 bought again 55 days later: outside a 30-day window.
    assert not outcomes.loc["u1", "repurchased"]


def test_repurchase_rate_by_first_delivery(deliveries):
    outcomes = metrics.first_delivery_outcomes(deliveries, orders_frame())
    rates = metrics.repurchase_rate(outcomes, ["first_delivery_late"]).set_index(
        "first_delivery_late"
    )

    assert rates.loc[True, "customers"] == 2
    assert rates.loc[True, "repurchase_pct"] == pytest.approx(50)


def test_monthly_revenue_splits_the_revenue_that_came_late(deliveries):
    monthly = metrics.monthly_revenue(deliveries).set_index("year_month")

    assert monthly.loc["2017-01", "revenue_brl"] == pytest.approx(216)
    assert monthly.loc["2017-01", "avg_ticket_brl"] == pytest.approx(108)
    assert monthly.loc["2017-01", "late_revenue_pct"] == pytest.approx(50)
    assert monthly.loc["2017-01", "freight_share_pct"] == pytest.approx(26 / 216 * 100)
    assert monthly.loc["2017-08", "late_revenue_pct"] == 0


def test_weekdays_follow_the_iso_numbering_of_the_sql(deliveries):
    result = metrics.late_rate_by_weekday(deliveries).set_index("purchase_weekday")

    assert list(result.index) == ["2. Tuesday", "3. Wednesday", "4. Thursday", "5. Friday"]
    assert result.loc["5. Friday", "late_pct"] == pytest.approx(100)
    assert result.loc["4. Thursday", "avg_seller_handling_days"] == pytest.approx(1.5)


def test_weekday_hour_volume_counts_every_delivery(deliveries):
    grid = metrics.weekday_hour_volume(deliveries)

    assert grid["deliveries"].sum() == len(deliveries)
    assert set(grid.columns) == {"purchase_weekday", "purchase_hour", "deliveries"}


def test_freight_share_is_the_median_of_freight_over_items(deliveries):
    result = metrics.freight_share_by_distance(deliveries).set_index("distance_band")

    assert result.loc["300-600", "median_freight_share_pct"] == pytest.approx(
        (20 + 18 / 90 * 100) / 2
    )
    assert result.loc["unknown", "avg_freight_value"] == pytest.approx(30)


def test_payment_types_are_ordered_by_volume_with_the_approval_median(deliveries):
    result = metrics.late_rate_by_payment_type(deliveries)

    assert list(result["payment_type"]) == ["credit_card", "boleto", "voucher"]
    boleto = result.set_index("payment_type").loc["boleto"]
    assert boleto["median_approval_hours"] == pytest.approx(60)
    assert boleto["late_pct"] == pytest.approx(100)


def test_review_comments_use_only_written_reviews(deliveries):
    result = metrics.review_comments_by_score(deliveries).set_index("score_group")

    assert list(result.index) == ["1-2", "4-5"]
    assert result.loc["1-2", "comments"] == 2
    assert result.loc["1-2", "mentions_delivery_pct"] == pytest.approx(50)
    assert result.loc["1-2", "late_pct"] == pytest.approx(100)


def test_seller_bands_weight_the_score_by_review(deliveries):
    sellers = metrics.seller_summary(deliveries, min_deliveries=2).set_index("seller_id")
    bands = metrics.seller_late_vs_review(deliveries, min_deliveries=2)

    assert list(sellers.index) == ["s1", "s2"]
    assert sellers.loc["s1", "late_pct"] == pytest.approx(100 / 3)
    assert list(bands["seller_late_band"]) == ["< 5", ">= 20"]
    assert bands.set_index("seller_late_band").loc[">= 20", "avg_review_score"] == pytest.approx(
        11 / 3
    )
