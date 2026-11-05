import pandas as pd

from olist_platform.analytics import charts, metrics
from tests.analytics_data import centroids_frame, deliveries_frame


def test_ramp_color_maps_extremes_to_the_lightest_and_darkest_steps():
    colors = charts.ramp_color(pd.Series([0.0, 5.0, 10.0]))

    assert colors[0] == charts.hex_to_rgb(charts.BLUE_RAMP[0])
    assert colors[-1] == charts.hex_to_rgb(charts.BLUE_RAMP[-1])


def test_ramp_color_handles_a_single_value():
    assert charts.ramp_color(pd.Series([3.0])) == [charts.hex_to_rgb(charts.BLUE_RAMP[0])]


def test_route_arcs_attach_centroids_and_drop_routes_without_them():
    routes = metrics.route_summary(deliveries_frame(), min_deliveries=1)
    centroids = centroids_frame()
    centroids = centroids[centroids["state"] != "BA"]

    arcs = charts.route_arcs(routes, centroids)

    assert len(arcs) == len(routes) - 1
    assert {"origin_lng", "destination_lat", "color", "width", "late_pct_label"} <= set(
        arcs.columns
    )
    assert arcs["width"].between(1, 10).all()


def test_band_charts_keep_the_band_order():
    freight = metrics.late_rate_by_freight(deliveries_frame())

    chart = charts.horizontal_bars(
        freight,
        "freight_band",
        "late_pct",
        category_title="Frete",
        value_title="% com atraso",
        sort_by_value=False,
    )

    assert chart.to_dict()["encoding"]["y"]["sort"] == list(freight["freight_band"].astype(str))


def test_group_label_matches_the_group_colors():
    labels = charts.group_label(pd.Series([True, False]))

    assert set(labels) == set(charts.GROUP_COLORS)
