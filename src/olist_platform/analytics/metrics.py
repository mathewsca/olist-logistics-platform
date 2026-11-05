"""SLA metrics over the ``deliveries`` and ``orders`` datasets.

Definitions follow the SQL in ``dbt/analyses/`` (same bands, same population), so the dashboard and
``docs/analises.md`` show the same numbers; the integration tests compare both.
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd

FREIGHT_BANDS = (
    (10, "< 10"),
    (15, "10-15"),
    (20, "15-20"),
    (30, "20-30"),
    (50, "30-50"),
    (np.inf, ">= 50"),
)
DISTANCE_BANDS = (
    (100, "< 100"),
    (300, "100-300"),
    (600, "300-600"),
    (1000, "600-1000"),
    (2000, "1000-2000"),
    (np.inf, ">= 2000"),
)
UNKNOWN_BAND = "unknown"
# Upper bound (inclusive) of delay_days for each band; delay_days <= 0 is on time.
DELAY_BANDS = (
    (-15, "15+ days early"),
    (-8, "8-14 days early"),
    (-1, "1-7 days early"),
    (0, "on the promised day"),
    (3, "1-3 days late"),
    (7, "4-7 days late"),
    (14, "8-14 days late"),
    (np.inf, "15+ days late"),
)
# Orders that never reached the customer do not count as a repurchase.
NOT_PURCHASED_STATUSES = ("canceled", "unavailable")
REPURCHASE_WINDOW = pd.Timedelta(days=180)
WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
# Upper bound (inclusive) of the review score of each group.
SCORE_GROUPS = ((2, "1-2"), (3, "3"), (5, "4-5"))
SELLER_LATE_BANDS = ((5, "< 5"), (10, "5-10"), (20, "10-20"), (np.inf, ">= 20"))
# A late rate over fewer deliveries is mostly noise.
MIN_SELLER_DELIVERIES = 30


@dataclass(frozen=True)
class SlaSummary:
    """Headline numbers of a set of deliveries."""

    deliveries: int
    late_pct: float
    median_delivery_days: float
    avg_promised_days: float
    avg_review_score: float


def pct(flags: pd.Series) -> float:
    """Share of true values, in percent."""
    return float(flags.astype(float).mean() * 100)


def share_pct(flags: pd.Series, keys) -> pd.Series:
    """Percent of true ``flags`` per group of ``keys`` (one or more aligned Series)."""
    return flags.astype(float).groupby(keys, observed=True).mean() * 100


def with_year_month(deliveries: pd.DataFrame) -> pd.DataFrame:
    """Adds ``year_month`` (YYYY-MM of the purchase), the grain of the monthly views."""
    return deliveries.assign(year_month=deliveries["purchased_at"].dt.strftime("%Y-%m"))


def sla_summary(deliveries: pd.DataFrame) -> SlaSummary:
    """Headline SLA numbers."""
    return SlaSummary(
        deliveries=len(deliveries),
        late_pct=pct(deliveries["is_late"]),
        median_delivery_days=float(deliveries["delivery_days"].median()),
        avg_promised_days=float(deliveries["estimated_delivery_days"].mean()),
        avg_review_score=float(deliveries["review_score"].mean()),
    )


def monthly_sla(deliveries: pd.DataFrame) -> pd.DataFrame:
    """One row per purchase month: volume, late %, average lateness of late orders, median days."""
    frame = with_year_month(deliveries)
    grouped = frame.groupby("year_month")
    result = pd.DataFrame(
        {
            "deliveries": grouped.size(),
            "late_pct": share_pct(frame["is_late"], frame["year_month"]),
            "avg_days_late_when_late": frame[frame["is_late"]]
            .groupby("year_month")["delay_days"]
            .mean(),
            "median_delivery_days": grouped["delivery_days"].median(),
            "avg_review_score": grouped["review_score"].mean().astype(float),
        }
    )
    return result.reset_index()


def band(values: pd.Series, bands: tuple[tuple[float, str], ...], right: bool) -> pd.Series:
    """Ordered categorical band of each value; missing values become ``unknown``."""
    edges = [-np.inf, *(upper for upper, _ in bands)]
    labels = [label for _, label in bands]
    banded = pd.cut(values.astype(float), bins=edges, labels=labels, right=right)
    if banded.isna().any():
        banded = banded.cat.add_categories(UNKNOWN_BAND).fillna(UNKNOWN_BAND)
    return banded


def late_rate_by(deliveries: pd.DataFrame, column: str | pd.Series) -> pd.DataFrame:
    """Deliveries and late % per value of ``column`` (a column name or an aligned Series)."""
    keys = deliveries[column] if isinstance(column, str) else column
    grouped = deliveries.groupby(keys, observed=True)
    result = pd.DataFrame(
        {
            "deliveries": grouped.size(),
            "late_pct": share_pct(deliveries["is_late"], keys),
            "avg_distance_km": grouped["distance_km"].mean(),
            "avg_freight_value": grouped["freight_value"].mean(),
        }
    )
    return result.rename_axis(keys.name).reset_index()


def late_rate_by_freight(deliveries: pd.DataFrame) -> pd.DataFrame:
    """Late % per freight band (BRL); bands are [lower, upper)."""
    bands = band(deliveries["freight_value"], FREIGHT_BANDS, right=False).rename("freight_band")
    return late_rate_by(deliveries, bands)


def late_rate_by_distance(deliveries: pd.DataFrame) -> pd.DataFrame:
    """Late % per distance band (km); bands are [lower, upper)."""
    bands = band(deliveries["distance_km"], DISTANCE_BANDS, right=False).rename("distance_band")
    return late_rate_by(deliveries, bands)


def late_rate_by_category(deliveries: pd.DataFrame, min_deliveries: int) -> pd.DataFrame:
    """Late % per product category with at least ``min_deliveries``, highest late % first."""
    categories = deliveries["main_product_category"].fillna(UNKNOWN_BAND).rename("product_category")
    result = late_rate_by(deliveries, categories)
    result = result[result["deliveries"] >= min_deliveries]
    return result.sort_values("late_pct", ascending=False, ignore_index=True)


def route_summary(deliveries: pd.DataFrame, min_deliveries: int) -> pd.DataFrame:
    """Seller state -> customer state routes with at least ``min_deliveries``, busiest first."""
    keys = [deliveries["origin_state"], deliveries["destination_state"]]
    grouped = deliveries.groupby(keys)
    result = pd.DataFrame(
        {
            "deliveries": grouped.size(),
            "late_pct": share_pct(deliveries["is_late"], keys),
            "avg_distance_km": grouped["distance_km"].mean(),
            "avg_promised_days": grouped["estimated_delivery_days"].mean(),
            "avg_delivery_days": grouped["delivery_days"].mean(),
        }
    ).reset_index()
    result = result[result["deliveries"] >= min_deliveries]
    return result.sort_values("deliveries", ascending=False, ignore_index=True)


def review_by_delay(deliveries: pd.DataFrame) -> pd.DataFrame:
    """Average score and % of 1-2 scores per delay band, among reviewed deliveries."""
    reviewed = deliveries[deliveries["review_score"].notna()]
    bands = band(reviewed["delay_days"], DELAY_BANDS, right=True).rename("delay_band")
    grouped = reviewed.groupby(bands, observed=True)
    result = pd.DataFrame(
        {
            "reviewed_deliveries": grouped.size(),
            "avg_review_score": grouped["review_score"].mean().astype(float),
            "low_score_pct": share_pct(reviewed["review_score"] <= 2, bands),
        }
    )
    return result.reset_index()


def slack_by_state(deliveries: pd.DataFrame) -> pd.DataFrame:
    """Promise slack (promised minus actual days) per customer state, most conservative first."""
    frame = deliveries.assign(
        slack_days=deliveries["estimated_delivery_days"] - deliveries["delivery_days"]
    )
    grouped = frame.groupby("destination_state")
    result = pd.DataFrame(
        {
            "deliveries": grouped.size(),
            "avg_promised_days": grouped["estimated_delivery_days"].mean(),
            "avg_delivery_days": grouped["delivery_days"].mean(),
            "median_slack_days": grouped["slack_days"].median(),
            "early_7_plus_pct": share_pct(frame["slack_days"] >= 7, frame["destination_state"]),
            "late_pct": share_pct(frame["is_late"], frame["destination_state"]),
        }
    ).reset_index()
    return result.sort_values("median_slack_days", ascending=False, ignore_index=True)


def first_delivery_outcomes(
    deliveries: pd.DataFrame, orders: pd.DataFrame, window: pd.Timedelta = REPURCHASE_WINDOW
) -> pd.DataFrame:
    """One row per customer: was the first delivered order late, did they buy again in ``window``.

    Only customers whose first delivered purchase has a full window before the last delivered
    purchase are kept, so recent customers do not look like they never came back.
    """
    # order_id breaks ties between orders placed at the same second (same rule as the SQL analysis).
    first = deliveries.sort_values(["purchased_at", "order_id"]).drop_duplicates(
        "customer_unique_id"
    )
    cutoff = deliveries["purchased_at"].max() - window
    first = first.loc[
        first["purchased_at"] <= cutoff,
        ["customer_unique_id", "order_id", "purchased_at", "is_late"],
    ]

    purchases = orders.loc[
        ~orders["order_status"].isin(NOT_PURCHASED_STATUSES), ["customer_unique_id", "purchased_at"]
    ]
    later = first.merge(purchases, on="customer_unique_id", suffixes=("_first", ""))
    in_window = (later["purchased_at"] > later["purchased_at_first"]) & (
        later["purchased_at"] <= later["purchased_at_first"] + window
    )
    returning = set(later.loc[in_window, "customer_unique_id"])

    return pd.DataFrame(
        {
            "customer_unique_id": first["customer_unique_id"],
            "first_order_id": first["order_id"],
            "cohort_month": first["purchased_at"].dt.strftime("%Y-%m"),
            "first_delivery_late": first["is_late"].astype(bool),
            "repurchased": first["customer_unique_id"].isin(returning),
        }
    ).reset_index(drop=True)


def repurchase_rate(outcomes: pd.DataFrame, by: list[str]) -> pd.DataFrame:
    """Customers and repurchase % per group of ``first_delivery_outcomes``."""
    keys = [outcomes[column] for column in by]
    result = pd.DataFrame(
        {
            "customers": outcomes.groupby(keys).size(),
            "repurchase_pct": share_pct(outcomes["repurchased"], keys),
        }
    )
    return result.reset_index()


def revenue(deliveries: pd.DataFrame) -> pd.Series:
    """Items plus freight of each delivered order (BRL)."""
    return deliveries["items_value"] + deliveries["freight_value"]


def monthly_revenue(deliveries: pd.DataFrame) -> pd.DataFrame:
    """Delivered revenue per purchase month, its freight share and the share delivered late."""
    frame = with_year_month(deliveries).assign(
        revenue_brl=revenue(deliveries),
        late_revenue=revenue(deliveries).where(deliveries["is_late"], 0.0),
    )
    grouped = frame.groupby("year_month")
    totals = grouped[["revenue_brl", "freight_value", "late_revenue"]].sum()
    result = pd.DataFrame(
        {
            "deliveries": grouped.size(),
            "revenue_brl": totals["revenue_brl"],
            "avg_ticket_brl": grouped["revenue_brl"].mean(),
            "freight_share_pct": totals["freight_value"] / totals["revenue_brl"] * 100,
            "late_revenue_pct": totals["late_revenue"] / totals["revenue_brl"] * 100,
        }
    )
    return result.reset_index()


def purchase_weekday(purchased_at: pd.Series) -> pd.Series:
    """``1. Monday`` ... ``7. Sunday``, the labels of the SQL analysis."""
    return purchased_at.dt.dayofweek.map(lambda day: f"{day + 1}. {WEEKDAYS[day]}")


def late_rate_by_weekday(deliveries: pd.DataFrame) -> pd.DataFrame:
    """Demand, late % and seller handling per weekday of the purchase."""
    keys = purchase_weekday(deliveries["purchased_at"]).rename("purchase_weekday")
    grouped = deliveries.groupby(keys)
    result = pd.DataFrame(
        {
            "deliveries": grouped.size(),
            "late_pct": share_pct(deliveries["is_late"], keys),
            "avg_seller_handling_days": grouped["seller_handling_days"].mean(),
            "avg_delivery_days": grouped["delivery_days"].mean(),
        }
    )
    return result.reset_index()


def weekday_hour_volume(deliveries: pd.DataFrame) -> pd.DataFrame:
    """Deliveries per weekday and hour of the purchase (the demand heatmap)."""
    keys = [
        purchase_weekday(deliveries["purchased_at"]).rename("purchase_weekday"),
        deliveries["purchased_at"].dt.hour.rename("purchase_hour"),
    ]
    return deliveries.groupby(keys).size().rename("deliveries").reset_index()


def freight_share_by_distance(deliveries: pd.DataFrame) -> pd.DataFrame:
    """Average freight and median freight / items value (%) per distance band."""
    priced = deliveries[deliveries["items_value"] > 0]
    bands = band(priced["distance_km"], DISTANCE_BANDS, right=False).rename("distance_band")
    share = (priced["freight_value"] / priced["items_value"] * 100).rename("freight_share")
    grouped = priced.groupby(bands, observed=True)
    result = pd.DataFrame(
        {
            "deliveries": grouped.size(),
            "avg_freight_value": grouped["freight_value"].mean(),
            "median_freight_share_pct": share.groupby(bands, observed=True).median(),
        }
    )
    return result.reset_index()


def late_rate_by_payment_type(deliveries: pd.DataFrame) -> pd.DataFrame:
    """Median hours to approval, delivery days and late % per main payment type."""
    keys = deliveries["main_payment_type"].fillna(UNKNOWN_BAND).rename("payment_type")
    approval_hours = (
        deliveries["approved_at"] - deliveries["purchased_at"]
    ).dt.total_seconds() / 3600
    grouped = deliveries.groupby(keys)
    result = pd.DataFrame(
        {
            "deliveries": grouped.size(),
            "median_approval_hours": approval_hours.groupby(keys).median(),
            "avg_delivery_days": grouped["delivery_days"].mean(),
            "late_pct": share_pct(deliveries["is_late"], keys),
        }
    ).reset_index()
    return result.sort_values(
        ["deliveries", "payment_type"], ascending=[False, True], ignore_index=True
    )


def review_comments_by_score(deliveries: pd.DataFrame) -> pd.DataFrame:
    """Written reviews per score group: share mentioning delivery and share of late orders."""
    comments = deliveries[deliveries["review_mentions_delivery"].notna()]
    groups = band(comments["review_score"], SCORE_GROUPS, right=True).rename("score_group")
    result = pd.DataFrame(
        {
            "comments": comments.groupby(groups, observed=True).size(),
            "mentions_delivery_pct": share_pct(comments["review_mentions_delivery"], groups),
            "late_pct": share_pct(comments["is_late"], groups),
        }
    )
    return result.reset_index()


def seller_summary(deliveries: pd.DataFrame, min_deliveries: int) -> pd.DataFrame:
    """One row per seller with at least ``min_deliveries``: volume, late % and average score."""
    grouped = deliveries.groupby("seller_id")
    result = pd.DataFrame(
        {
            "deliveries": grouped.size(),
            "late_pct": share_pct(deliveries["is_late"], deliveries["seller_id"]),
            "avg_review_score": grouped["review_score"].mean().astype(float),
            "score_sum": grouped["review_score"].sum().astype(float),
            "reviews": grouped["review_score"].count(),
        }
    ).reset_index()
    return result[result["deliveries"] >= min_deliveries].reset_index(drop=True)


def seller_late_vs_review(
    deliveries: pd.DataFrame, min_deliveries: int = MIN_SELLER_DELIVERIES
) -> pd.DataFrame:
    """Sellers banded by late %: how many, their deliveries and the score of their reviews."""
    sellers = seller_summary(deliveries, min_deliveries)
    bands = band(sellers["late_pct"], SELLER_LATE_BANDS, right=False).rename("seller_late_band")
    grouped = sellers.groupby(bands, observed=True)
    result = pd.DataFrame(
        {
            "sellers": grouped.size(),
            "deliveries": grouped["deliveries"].sum(),
            "avg_review_score": grouped["score_sum"].sum() / grouped["reviews"].sum(),
        }
    )
    return result.reset_index()
