"""Seller track record as known at purchase time: point in time (training) or snapshot (serving)."""

import numpy as np
import pandas as pd

SELLER_HISTORY_COLUMNS = (
    "seller_prior_deliveries",
    "seller_prior_late_rate",
    "seller_prior_mean_delivery_days",
)
# Pseudo-deliveries pulling a new seller's late rate towards the platform rate: with 1 or 2
# orders the raw rate is 0% or 100%, which says little about the seller.
SMOOTHING_WEIGHT = 10.0
PLATFORM_KEY = "__platform__"
# merge_asof needs both time keys in the same resolution; pandas 3 infers it per source.
TIMESTAMP_DTYPE = "datetime64[ns]"

DELIVERY_EVENT_COLUMNS = ("seller_id", "delivered_at", "is_late", "delivery_days")


def _history_features(
    count: pd.Series, late: pd.Series, days: pd.Series, platform_rate: pd.Series
) -> pd.DataFrame:
    count = count.fillna(0).astype(float)
    platform_rate = platform_rate.fillna(0).astype(float)
    late = late.fillna(0).astype(float)
    return pd.DataFrame(
        {
            "seller_prior_deliveries": count,
            "seller_prior_late_rate": (late + SMOOTHING_WEIGHT * platform_rate)
            / (count + SMOOTHING_WEIGHT),
            "seller_prior_mean_delivery_days": days.astype(float) / count.where(count > 0),
        }
    )


def _cumulative(events: pd.DataFrame, by: str | None) -> pd.DataFrame:
    """Running totals after each delivery, overall or per ``by`` key."""
    events = events.sort_values("delivered_at", kind="stable")
    if by is None:
        return events[["delivered_at"]].assign(
            count=np.arange(1, len(events) + 1),
            late=events["is_late"].cumsum(),
            days=events["delivery_days"].cumsum(),
        )
    group = events.groupby(by, sort=False)
    return events[["delivered_at", by]].assign(
        count=group.cumcount() + 1,
        late=group["is_late"].cumsum(),
        days=group["delivery_days"].cumsum(),
    )


def _as_events(deliveries: pd.DataFrame) -> pd.DataFrame:
    events = deliveries[list(DELIVERY_EVENT_COLUMNS)].copy()
    # One string dtype on both sides: merge_asof refuses to match str against object keys.
    events["seller_id"] = events["seller_id"].astype("string")
    events["delivered_at"] = pd.to_datetime(events["delivered_at"]).astype(TIMESTAMP_DTYPE)
    events["is_late"] = events["is_late"].astype(float)
    events["delivery_days"] = events["delivery_days"].astype(float)
    return events.dropna(subset=["delivered_at"])


def point_in_time_history(orders: pd.DataFrame, deliveries: pd.DataFrame) -> pd.DataFrame:
    """History of each order's seller using only deliveries completed strictly before its purchase.

    Ordering by purchase date is not enough: an earlier order still in transit at purchase time
    had an unknown outcome, so counting it would leak the future.
    """
    events = _as_events(deliveries)
    left = pd.DataFrame(
        {
            "row": np.arange(len(orders)),
            "seller_id": orders["seller_id"].astype("string").reset_index(drop=True),
            "purchased_at": pd.to_datetime(orders["purchased_at"])
            .astype(TIMESTAMP_DTYPE)
            .to_numpy(),
        }
    ).sort_values("purchased_at", kind="stable")

    asof = {"left_on": "purchased_at", "right_on": "delivered_at", "allow_exact_matches": False}
    seller = pd.merge_asof(left, _cumulative(events, "seller_id"), by="seller_id", **asof)
    platform = pd.merge_asof(left, _cumulative(events, None), **asof)
    platform_rate = platform["late"] / platform["count"]

    history = _history_features(seller["count"], seller["late"], seller["days"], platform_rate)
    history.index = left["row"].to_numpy()
    history = history.sort_index()
    history.index = orders.index
    return history


def history_snapshot(deliveries: pd.DataFrame, as_of: pd.Timestamp) -> pd.DataFrame:
    """Per-seller history frozen at ``as_of``, plus a ``__platform__`` row for unseen sellers."""
    events = _as_events(deliveries)
    events = events[events["delivered_at"] < pd.Timestamp(as_of)]
    totals = events.groupby("seller_id").agg(
        count=("is_late", "size"), late=("is_late", "sum"), days=("delivery_days", "sum")
    )
    platform_rate = events["is_late"].mean() if len(events) else 0.0
    rates = pd.Series(platform_rate, index=totals.index)
    snapshot = _history_features(totals["count"], totals["late"], totals["days"], rates)
    snapshot.index = totals.index
    empty = pd.Series([np.nan])
    snapshot.loc[PLATFORM_KEY] = _history_features(
        empty, empty, empty, pd.Series([platform_rate])
    ).iloc[0]
    snapshot.index.name = "seller_id"
    return snapshot


def lookup_history(seller_ids: pd.Series, snapshot: pd.DataFrame) -> pd.DataFrame:
    """History columns for each seller from a snapshot; unseen sellers get the platform row."""
    known = seller_ids.where(seller_ids.isin(snapshot.index), PLATFORM_KEY)
    history = snapshot.loc[known.to_numpy(), list(SELLER_HISTORY_COLUMNS)]
    history.index = seller_ids.index
    return history
