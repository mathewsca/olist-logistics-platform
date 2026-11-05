"""Altair and pydeck builders for the dashboard, with one color convention for every page.

Magnitude is one hue (blue); the only two-group comparison (late vs on-time first delivery) uses
the first two categorical slots. Volume and rates are never mixed on one axis: they get two charts.
"""

import altair as alt
import numpy as np
import pandas as pd

BLUE = "#2a78d6"
ORANGE = "#eb6834"
# Sequential blue ramp (light -> dark) for the route map, from the reference palette.
BLUE_RAMP = ("#86b6ef", "#5598e7", "#2a78d6", "#1c5cab", "#104281", "#0d366b")
GROUP_COLORS = {"No prazo": BLUE, "Com atraso": ORANGE}


def horizontal_bars(
    frame: pd.DataFrame,
    category: str,
    value: str,
    *,
    category_title: str,
    value_title: str,
    sort_by_value: bool = True,
    value_format: str = ".1f",
    tooltip_extra: tuple[str, ...] = (),
) -> alt.Chart:
    """One bar per category, longest first unless the categories are ordered bands."""
    # Bands keep the frame's order; Altair would otherwise sort "< 10", ">= 50", "10-15" as text.
    sort = "-x" if sort_by_value else list(frame[category].astype(str))
    return (
        alt.Chart(frame)
        .mark_bar(color=BLUE, cornerRadiusEnd=4, height={"band": 0.7})
        .encode(
            y=alt.Y(f"{category}:N", title=category_title, sort=sort),
            x=alt.X(f"{value}:Q", title=value_title),
            tooltip=[
                alt.Tooltip(f"{category}:N", title=category_title),
                alt.Tooltip(f"{value}:Q", title=value_title, format=value_format),
                *(alt.Tooltip(column) for column in tooltip_extra),
            ],
        )
    )


def monthly_line(
    frame: pd.DataFrame, value: str, *, value_title: str, value_format: str = ".1f"
) -> alt.Chart:
    """One measure by purchase month."""
    base = alt.Chart(frame).encode(
        x=alt.X("year_month:O", title="Mês de compra", axis=alt.Axis(labelAngle=-45)),
        y=alt.Y(f"{value}:Q", title=value_title),
        tooltip=[
            alt.Tooltip("year_month:O", title="Mês"),
            alt.Tooltip(f"{value}:Q", title=value_title, format=value_format),
        ],
    )
    return base.mark_line(color=BLUE, strokeWidth=2) + base.mark_point(
        color=BLUE, filled=True, size=64
    )


def monthly_columns(frame: pd.DataFrame, value: str, *, value_title: str) -> alt.Chart:
    """Volume by purchase month."""
    return (
        alt.Chart(frame)
        .mark_bar(color=BLUE, cornerRadiusEnd=4)
        .encode(
            x=alt.X("year_month:O", title="Mês de compra", axis=alt.Axis(labelAngle=-45)),
            y=alt.Y(f"{value}:Q", title=value_title),
            tooltip=[
                alt.Tooltip("year_month:O", title="Mês"),
                alt.Tooltip(f"{value}:Q", title=value_title, format=",d"),
            ],
        )
    )


def heatmap(
    frame: pd.DataFrame, x: str, y: str, value: str, *, x_title: str, y_title: str, value_title: str
) -> alt.Chart:
    """Magnitude of ``value`` on an ``x`` × ``y`` grid, in the sequential blue ramp."""
    return (
        alt.Chart(frame)
        .mark_rect()
        .encode(
            x=alt.X(f"{x}:O", title=x_title),
            y=alt.Y(f"{y}:O", title=y_title),
            color=alt.Color(
                f"{value}:Q", title=value_title, scale=alt.Scale(range=list(BLUE_RAMP))
            ),
            tooltip=[
                alt.Tooltip(f"{y}:O", title=y_title),
                alt.Tooltip(f"{x}:O", title=x_title),
                alt.Tooltip(f"{value}:Q", title=value_title, format=",d"),
            ],
        )
    )


def scatter(
    frame: pd.DataFrame,
    x: str,
    y: str,
    size: str,
    *,
    x_title: str,
    y_title: str,
    size_title: str,
    tooltip_extra: tuple[str, ...] = (),
) -> alt.Chart:
    """One translucent point per row; point area follows ``size``."""
    return (
        alt.Chart(frame)
        .mark_circle(color=BLUE, opacity=0.45)
        .encode(
            x=alt.X(f"{x}:Q", title=x_title),
            y=alt.Y(f"{y}:Q", title=y_title, scale=alt.Scale(zero=False)),
            size=alt.Size(f"{size}:Q", title=size_title),
            tooltip=[
                *(alt.Tooltip(column) for column in tooltip_extra),
                alt.Tooltip(f"{x}:Q", title=x_title, format=".1f"),
                alt.Tooltip(f"{y}:Q", title=y_title, format=".2f"),
                alt.Tooltip(f"{size}:Q", title=size_title, format=",d"),
            ],
        )
    )


def group_label(first_delivery_late: pd.Series) -> pd.Series:
    """Readable label of the late / on-time groups, matching ``GROUP_COLORS``."""
    return first_delivery_late.map({True: "Com atraso", False: "No prazo"})


def grouped_monthly_lines(
    frame: pd.DataFrame, value: str, group: str, *, value_title: str, group_title: str
) -> alt.Chart:
    """One line per group by month, with a legend (two series)."""
    color = alt.Color(
        f"{group}:N",
        title=group_title,
        scale=alt.Scale(domain=list(GROUP_COLORS), range=list(GROUP_COLORS.values())),
        legend=alt.Legend(orient="top"),
    )
    base = alt.Chart(frame).encode(
        x=alt.X("cohort_month:O", title="Mês da primeira compra", axis=alt.Axis(labelAngle=-45)),
        y=alt.Y(f"{value}:Q", title=value_title),
        color=color,
        tooltip=[
            alt.Tooltip("cohort_month:O", title="Mês"),
            alt.Tooltip(f"{group}:N", title=group_title),
            alt.Tooltip(f"{value}:Q", title=value_title, format=".2f"),
            alt.Tooltip("customers:Q", title="Clientes", format=",d"),
        ],
    )
    return base.mark_line(strokeWidth=2) + base.mark_point(filled=True, size=64)


def ramp_color(values: pd.Series) -> list[list[int]]:
    """RGB of each value on the sequential blue ramp (min -> lightest, max -> darkest)."""
    low, high = float(values.min()), float(values.max())
    span = high - low or 1.0
    steps = np.clip(((values - low) / span * (len(BLUE_RAMP) - 1)).round(), 0, len(BLUE_RAMP) - 1)
    return [hex_to_rgb(BLUE_RAMP[int(step)]) for step in steps]


def hex_to_rgb(color: str) -> list[int]:
    """``#rrggbb`` as ``[r, g, b]``, the format pydeck expects."""
    return [int(color[i : i + 2], 16) for i in (1, 3, 5)]


def route_arcs(routes: pd.DataFrame, centroids: pd.DataFrame) -> pd.DataFrame:
    """Routes with origin/destination coordinates (state centroids), arc color and width."""
    coordinates = centroids.set_index("state")[["longitude", "latitude"]]
    arcs = routes.join(coordinates, on="origin_state").rename(
        columns={"longitude": "origin_lng", "latitude": "origin_lat"}
    )
    arcs = arcs.join(coordinates, on="destination_state").rename(
        columns={"longitude": "destination_lng", "latitude": "destination_lat"}
    )
    arcs = arcs.dropna(subset=["origin_lng", "destination_lng"]).reset_index(drop=True)
    arcs["color"] = ramp_color(arcs["late_pct"])
    arcs["width"] = 1 + 9 * np.sqrt(arcs["deliveries"] / arcs["deliveries"].max())
    arcs["late_pct_label"] = arcs["late_pct"].map(lambda v: f"{v:.1f}%")
    return arcs
