"""Turn the raw attributes of an order, as known at purchase time, into model features."""

import numpy as np
import pandas as pd

from olist_platform.features.seller_history import SELLER_HISTORY_COLUMNS

EARTH_RADIUS_KM = 6371.0

# What the caller (training query or API request) must provide. Anything known only after the
# purchase (approval, carrier, delivery, review) is deliberately absent; see docs/model_card.md.
RAW_INPUT_COLUMNS = (
    "purchased_at",
    "estimated_delivery_date",
    "items_value",
    "freight_value",
    "item_count",
    "seller_count",
    "total_weight_g",
    "total_volume_cm3",
    "max_side_cm",
    "main_product_category",
    "origin_state",
    "destination_state",
    "origin_latitude",
    "origin_longitude",
    "destination_latitude",
    "destination_longitude",
    *SELLER_HISTORY_COLUMNS,
)

NUMERIC_FEATURES = (
    "estimated_delivery_days",
    "distance_km",
    "km_per_estimated_day",
    "items_value",
    "freight_value",
    "freight_ratio",
    "item_count",
    "seller_count",
    "total_weight_g",
    "total_volume_cm3",
    "max_side_cm",
    "is_same_state",
    "purchase_month",
    "purchase_day_of_week",
    "purchase_hour",
    *SELLER_HISTORY_COLUMNS,
)
CATEGORICAL_FEATURES = ("origin_state", "destination_state", "main_product_category")
FEATURE_COLUMNS = (*NUMERIC_FEATURES, *CATEGORICAL_FEATURES)


def haversine_km(lat1: pd.Series, lng1: pd.Series, lat2: pd.Series, lng2: pd.Series) -> pd.Series:
    """Great-circle distance, the same formula as the dbt macro behind ``fct_deliveries``."""
    lat1, lng1, lat2, lng2 = (np.radians(s.astype(float)) for s in (lat1, lng1, lat2, lng2))
    a = (
        np.sin((lat2 - lat1) / 2) ** 2
        + np.cos(lat1) * np.cos(lat2) * np.sin((lng2 - lng1) / 2) ** 2
    )
    return 2 * EARTH_RADIUS_KM * np.arcsin(np.sqrt(a))


def _same_state(origin: pd.Series, destination: pd.Series) -> pd.Series:
    # A missing state is unknown, not "different states": leave it to the pipeline's imputer.
    same = (origin == destination).astype(float)
    return same.where(origin.notna() & destination.notna())


def build_features(orders: pd.DataFrame) -> pd.DataFrame:
    """Feature matrix with ``FEATURE_COLUMNS``, one row per input row, index preserved."""
    missing = [column for column in RAW_INPUT_COLUMNS if column not in orders.columns]
    if missing:
        raise ValueError(f"Missing input columns: {', '.join(missing)}")

    purchased_at = pd.to_datetime(orders["purchased_at"])
    # The promise is a calendar date, so the horizon is counted in calendar days (as in the marts).
    estimated_days = (
        pd.to_datetime(orders["estimated_delivery_date"]).dt.normalize()
        - purchased_at.dt.normalize()
    ).dt.days.astype(float)
    distance = haversine_km(
        orders["origin_latitude"],
        orders["origin_longitude"],
        orders["destination_latitude"],
        orders["destination_longitude"],
    )
    items_value = orders["items_value"].astype(float)
    freight_value = orders["freight_value"].astype(float)

    features = pd.DataFrame(
        {
            "estimated_delivery_days": estimated_days,
            "distance_km": distance,
            # How hard the promise is: a long route with a short promise is the textbook late order.
            "km_per_estimated_day": distance / estimated_days.where(estimated_days > 0),
            "items_value": items_value,
            "freight_value": freight_value,
            "freight_ratio": freight_value / items_value.where(items_value > 0),
            "item_count": orders["item_count"].astype(float),
            "seller_count": orders["seller_count"].astype(float),
            "total_weight_g": orders["total_weight_g"].astype(float),
            "total_volume_cm3": orders["total_volume_cm3"].astype(float),
            "max_side_cm": orders["max_side_cm"].astype(float),
            "is_same_state": _same_state(orders["origin_state"], orders["destination_state"]),
            "purchase_month": purchased_at.dt.month.astype(float),
            "purchase_day_of_week": purchased_at.dt.day_of_week.astype(float),
            "purchase_hour": purchased_at.dt.hour.astype(float),
        },
        index=orders.index,
    )
    for column in SELLER_HISTORY_COLUMNS:
        features[column] = orders[column].astype(float)
    for column in CATEGORICAL_FEATURES:
        # NaN rather than None: scikit-learn imputers and encoders only recognise NaN as missing.
        features[column] = orders[column].astype(object).where(orders[column].notna(), np.nan)
    return features[list(FEATURE_COLUMNS)]
