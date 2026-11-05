"""Training-serving parity on the real marts: items aggregated as the API does = training query."""

import numpy as np
import pandas as pd
import psycopg
import pytest

from olist_platform.api.bundle import ModelBundle
from olist_platform.api.schemas import OrderRequest
from olist_platform.api.service import raw_inputs
from olist_platform.features import (
    SELLER_HISTORY_COLUMNS,
    aggregate_items,
    attach_coordinates,
    build_features,
    history_snapshot,
)
from olist_platform.ingestion.settings import WarehouseSettings, load_dotenv_if_present
from olist_platform.models.data import DELIVERIES_SQL

pytestmark = pytest.mark.integration

ITEMS_SQL = """
    select
        items.order_id as order_key,
        items.seller_id,
        sellers.seller_zip_code_prefix,
        sellers.seller_state,
        items.price,
        items.freight_value,
        items.product_category,
        products.product_weight_g,
        products.product_length_cm,
        products.product_height_cm,
        products.product_width_cm
    from marts.fct_order_items as items
    inner join marts.dim_sellers as sellers on items.seller_id = sellers.seller_id
    left join marts.dim_products as products on items.product_id = products.product_id
    where items.order_id in (select order_id from marts.fct_deliveries)
    order by items.order_id, items.order_item_id
"""
DESTINATIONS_SQL = """
    select order_id, destination_zip_code_prefix, destination_state
    from marts.fct_deliveries
"""
OPTIONAL_ITEM_COLUMNS = (
    "product_category",
    "product_weight_g",
    "product_length_cm",
    "product_height_cm",
    "product_width_cm",
)
GEOGRAPHY_SQL = "select zip_code_prefix, latitude, longitude from marts.dim_geography"


def _query(conn, sql: str) -> pd.DataFrame:
    cursor = conn.execute(sql)
    frame = pd.DataFrame(cursor.fetchall(), columns=[c.name for c in cursor.description])
    for column in frame.columns:
        if frame[column].map(type).astype(str).str.contains("Decimal").any():
            frame[column] = frame[column].astype(float)
    return frame


@pytest.fixture(scope="module")
def frames():
    load_dotenv_if_present()
    try:
        conn = psycopg.connect(WarehouseSettings.from_env().conninfo())
    except psycopg.OperationalError as error:
        pytest.fail(f"Warehouse not reachable (did you run `make up`?): {error}")
    with conn:
        return {
            "training": _query(conn, DELIVERIES_SQL)
            .astype({"purchased_at": "datetime64[us]", "estimated_delivery_date": "datetime64[us]"})
            .set_index("order_id"),
            "items": _query(conn, ITEMS_SQL),
            "destinations": _query(conn, DESTINATIONS_SQL).set_index("order_id"),
            "geography": _query(conn, GEOGRAPHY_SQL).set_index("zip_code_prefix"),
        }


def _serving_inputs(frames) -> pd.DataFrame:
    orders = aggregate_items(frames["items"]).join(frames["destinations"])
    orders = attach_coordinates(orders, frames["geography"])
    training = frames["training"].loc[orders.index]
    orders["purchased_at"] = training["purchased_at"]
    orders["estimated_delivery_date"] = training["estimated_delivery_date"]
    return orders


def test_aggregated_items_match_the_training_query(frames):
    serving = _serving_inputs(frames)
    training = frames["training"].loc[serving.index]
    assert len(serving) == len(frames["training"])
    for column in ("seller_id", "main_product_category", "origin_state", "destination_state"):
        pd.testing.assert_series_equal(
            serving[column].astype(object), training[column].astype(object), check_names=False
        )
    for column in (
        "item_count",
        "seller_count",
        "items_value",
        "freight_value",
        "total_weight_g",
        "total_volume_cm3",
        "max_side_cm",
        "origin_latitude",
        "destination_longitude",
    ):
        np.testing.assert_allclose(
            serving[column].astype(float), training[column].astype(float), err_msg=column
        )


def _requests(frames, order_ids) -> list[OrderRequest]:
    """Real orders rewritten as API requests: one item per source row, CEP prefixes, local time."""
    training = frames["training"]
    destinations = frames["destinations"]
    items = frames["items"].set_index("order_key")
    requests = []
    for order_id in order_ids:
        rows = items.loc[[order_id]]
        requests.append(
            OrderRequest(
                purchased_at=training.at[order_id, "purchased_at"].to_pydatetime(),
                estimated_delivery_date=training.at[order_id, "estimated_delivery_date"].date(),
                customer_zip_code=destinations.at[order_id, "destination_zip_code_prefix"],
                customer_state=destinations.at[order_id, "destination_state"],
                items=[
                    {
                        "seller_id": row.seller_id,
                        "seller_zip_code": row.seller_zip_code_prefix,
                        "seller_state": row.seller_state,
                        "price": row.price,
                        "freight_value": row.freight_value,
                        **{
                            column: None if pd.isna(getattr(row, column)) else getattr(row, column)
                            for column in OPTIONAL_ITEM_COLUMNS
                        },
                    }
                    for row in rows.itertuples()
                ],
            )
        )
    return requests


def test_api_requests_rebuild_the_training_features(frames):
    training = frames["training"]
    valid = training[
        training["estimated_delivery_date"].dt.normalize()
        >= training["purchased_at"].dt.normalize()
    ]
    order_ids = valid.sample(n=3000, random_state=0).index
    bundle = ModelBundle(
        classifier=None,
        regressor=None,
        threshold=0.5,
        # History is held equal below; an empty snapshot still has the platform row lookups need.
        seller_history=history_snapshot(
            pd.DataFrame(columns=["seller_id", "delivered_at", "is_late", "delivery_days"]),
            pd.Timestamp("2018-01-01"),
        ),
        geography=frames["geography"],
        metadata={},
    )
    served = raw_inputs(_requests(frames, order_ids), bundle)
    served.index = order_ids
    expected = training.loc[order_ids].copy()
    for column in SELLER_HISTORY_COLUMNS:
        served[column] = 0.0
        expected[column] = 0.0
    pd.testing.assert_frame_equal(
        build_features(served), build_features(expected), check_index_type=False, check_names=False
    )


def test_features_match_the_training_query(frames):
    serving = _serving_inputs(frames)
    training = frames["training"].loc[serving.index].copy()
    # Seller history has its own parity test (snapshot x point in time); here it is held equal.
    for column in SELLER_HISTORY_COLUMNS:
        serving[column] = 0.0
        training[column] = 0.0
    pd.testing.assert_frame_equal(
        build_features(serving), build_features(training), check_index_type=False, check_names=False
    )
