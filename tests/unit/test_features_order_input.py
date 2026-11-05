import math

import pandas as pd
import pytest

from olist_platform.features import ORDER_ITEM_COLUMNS, aggregate_items, attach_coordinates


def item(order_key="o1", **overrides):
    row = {
        "order_key": order_key,
        "seller_id": "s1",
        "seller_zip_code_prefix": "01001",
        "seller_state": "SP",
        "price": 50.0,
        "freight_value": 10.0,
        "product_category": "housewares",
        "product_weight_g": 500.0,
        "product_length_cm": 10.0,
        "product_height_cm": 20.0,
        "product_width_cm": 30.0,
    }
    row.update(overrides)
    return row


def items(*rows):
    return pd.DataFrame(list(rows), columns=list(ORDER_ITEM_COLUMNS))


def test_sums_and_counts_per_order():
    summary = aggregate_items(
        items(item(), item(seller_id="s2", price=30.0, freight_value=5.0), item("o2"))
    )
    first = summary.loc["o1"]
    assert first["item_count"] == 2
    assert first["seller_count"] == 2
    assert first["items_value"] == pytest.approx(80.0)
    assert first["freight_value"] == pytest.approx(15.0)
    assert first["total_weight_g"] == pytest.approx(1000.0)
    assert first["total_volume_cm3"] == pytest.approx(12000.0)
    assert first["max_side_cm"] == 30
    assert list(summary.index) == ["o1", "o2"]


def test_main_item_is_the_most_expensive_and_ties_keep_the_first():
    summary = aggregate_items(
        items(
            item(seller_id="cheap", price=10.0, product_category="toys"),
            item(seller_id="first", price=90.0, seller_state="RJ", seller_zip_code_prefix="20000"),
            item(seller_id="tied", price=90.0, seller_state="MG"),
        )
    )
    row = summary.loc["o1"]
    assert row["seller_id"] == "first"
    assert row["origin_state"] == "RJ"
    assert row["origin_zip_code_prefix"] == "20000"
    assert row["main_product_category"] == "housewares"


def test_missing_product_attributes_follow_sql_null_rules():
    summary = aggregate_items(
        items(
            item(product_weight_g=None, product_length_cm=None, product_height_cm=40.0),
            item(product_weight_g=None),
        )
    )
    row = summary.loc["o1"]
    assert math.isnan(row["total_weight_g"])
    # The first product has no volume (a missing side) but still contributes its longest side.
    assert row["total_volume_cm3"] == pytest.approx(6000.0)
    assert row["max_side_cm"] == 40


def test_missing_item_column_fails_explicitly():
    with pytest.raises(ValueError, match="price"):
        aggregate_items(items(item()).drop(columns="price"))


def test_attach_coordinates_leaves_unknown_prefixes_missing():
    geography = pd.DataFrame(
        {"latitude": [-23.5], "longitude": [-46.6]},
        index=pd.Index(["01001"], name="zip_code_prefix"),
    )
    orders = pd.DataFrame(
        {"origin_zip_code_prefix": ["01001"], "destination_zip_code_prefix": ["99999"]},
        index=["o1"],
    )
    result = attach_coordinates(orders, geography)
    assert result.loc["o1", "origin_latitude"] == pytest.approx(-23.5)
    assert math.isnan(result.loc["o1", "destination_longitude"])
