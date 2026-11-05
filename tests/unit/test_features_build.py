import math

import pandas as pd
import pytest

from olist_platform.features import FEATURE_COLUMNS, RAW_INPUT_COLUMNS, build_features
from olist_platform.features.build import haversine_km

# Known after the purchase; none may reach the model.
POST_PURCHASE_COLUMNS = {
    "approved_at",
    "delivered_to_carrier_at",
    "delivered_to_customer_at",
    "delivery_date",
    "delivery_days",
    "delay_days",
    "is_late",
    "seller_handling_days",
    "carrier_transit_days",
    "review_score",
    "shipping_limit_at",
    "order_status",
}


def raw_order(**overrides):
    row = {
        "purchased_at": "2018-03-05 14:30:00",
        "estimated_delivery_date": "2018-03-25",
        "items_value": 100.0,
        "freight_value": 20.0,
        "item_count": 2,
        "seller_count": 1,
        "total_weight_g": 1500,
        "total_volume_cm3": 8000,
        "max_side_cm": 30,
        "main_product_category": "health_beauty",
        "origin_state": "SP",
        "destination_state": "RJ",
        "origin_latitude": -23.55,
        "origin_longitude": -46.63,
        "destination_latitude": -22.91,
        "destination_longitude": -43.17,
        "seller_prior_deliveries": 12.0,
        "seller_prior_late_rate": 0.08,
        "seller_prior_mean_delivery_days": 9.5,
    }
    row.update(overrides)
    return pd.DataFrame([row])


def test_inputs_and_features_exclude_post_purchase_information():
    assert not POST_PURCHASE_COLUMNS & set(RAW_INPUT_COLUMNS)
    assert not POST_PURCHASE_COLUMNS & set(FEATURE_COLUMNS)
    assert not [c for c in (*RAW_INPUT_COLUMNS, *FEATURE_COLUMNS) if c.startswith("review_")]


def test_extra_columns_in_the_input_are_ignored():
    features = build_features(raw_order(delivery_days=3.0, is_late=True))
    assert list(features.columns) == list(FEATURE_COLUMNS)


def test_missing_input_column_fails_explicitly():
    with pytest.raises(ValueError, match="estimated_delivery_date"):
        build_features(raw_order().drop(columns="estimated_delivery_date"))


def test_derived_features():
    row = build_features(raw_order()).iloc[0]
    assert row["estimated_delivery_days"] == 20
    assert row["freight_ratio"] == pytest.approx(0.2)
    assert row["is_same_state"] == 0
    assert row["purchase_month"] == 3
    assert row["purchase_day_of_week"] == 0
    assert row["purchase_hour"] == 14
    assert row["distance_km"] == pytest.approx(357, abs=5)
    assert row["km_per_estimated_day"] == pytest.approx(row["distance_km"] / 20)


def test_promise_counts_calendar_days_not_hours():
    late_evening = build_features(raw_order(purchased_at="2018-03-05 23:59:00")).iloc[0]
    assert late_evening["estimated_delivery_days"] == 20


def test_missing_values_become_nan_not_errors():
    row = build_features(
        raw_order(origin_latitude=None, items_value=0.0, main_product_category=None)
    ).iloc[0]
    assert math.isnan(row["distance_km"])
    assert math.isnan(row["km_per_estimated_day"])
    assert math.isnan(row["freight_ratio"])
    assert pd.isna(row["main_product_category"])


def test_missing_state_leaves_is_same_state_unknown():
    row = build_features(raw_order(origin_state=None)).iloc[0]
    assert math.isnan(row["is_same_state"])


def test_haversine_zero_for_the_same_point():
    lat, lng = pd.Series([-23.5]), pd.Series([-46.6])
    assert haversine_km(lat, lng, lat, lng).iloc[0] == pytest.approx(0)
