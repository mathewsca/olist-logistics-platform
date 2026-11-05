"""Training data from the marts: raw purchase-time inputs, labels and the seller history."""

from dataclasses import dataclass
from decimal import Decimal

import pandas as pd

from olist_platform.features import point_in_time_history

# Window with enough monthly volume (docs/dados.md); the sparse 2016 months only feed the history.
WINDOW_START = pd.Timestamp("2017-01-01")
WINDOW_END = pd.Timestamp("2018-09-01")

# delivered_to_customer_at is read for the labels and the seller history only, never as a feature.
DELIVERIES_SQL = """
    with order_products as (
        select
            items.order_id,
            sum(products.product_weight_g) as total_weight_g,
            sum(products.product_volume_cm3) as total_volume_cm3,
            max(greatest(
                products.product_length_cm, products.product_height_cm, products.product_width_cm
            )) as max_side_cm
        from marts.fct_order_items as items
        left join marts.dim_products as products
            on items.product_id = products.product_id
        group by items.order_id
    )

    select
        deliveries.order_id,
        deliveries.seller_id,
        deliveries.purchased_at,
        deliveries.estimated_delivery_date,
        deliveries.delivered_to_customer_at,
        deliveries.is_late,
        deliveries.delivery_days,
        deliveries.items_value,
        deliveries.freight_value,
        deliveries.item_count,
        deliveries.seller_count,
        deliveries.main_product_category,
        deliveries.origin_state,
        deliveries.destination_state,
        -- Not a feature: monitoring slices metrics by the customer's region.
        deliveries.destination_region,
        origin.latitude as origin_latitude,
        origin.longitude as origin_longitude,
        destination.latitude as destination_latitude,
        destination.longitude as destination_longitude,
        order_products.total_weight_g,
        order_products.total_volume_cm3,
        order_products.max_side_cm
    from marts.fct_deliveries as deliveries
    left join marts.dim_geography as origin
        on deliveries.origin_zip_code_prefix = origin.zip_code_prefix
    left join marts.dim_geography as destination
        on deliveries.destination_zip_code_prefix = destination.zip_code_prefix
    left join order_products
        on deliveries.order_id = order_products.order_id
"""


@dataclass(frozen=True)
class TrainingData:
    """Modelling rows inside the window, plus every delivery (the source of seller history)."""

    rows: pd.DataFrame
    deliveries: pd.DataFrame


def _normalize(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.copy()
    for column in frame.columns:
        values = frame[column].dropna()
        if not values.empty and isinstance(values.iloc[0], Decimal):
            frame[column] = frame[column].astype(float)
    frame["purchased_at"] = pd.to_datetime(frame["purchased_at"])
    frame["delivered_to_customer_at"] = pd.to_datetime(frame["delivered_to_customer_at"])
    frame["estimated_delivery_date"] = pd.to_datetime(frame["estimated_delivery_date"])
    frame["is_late"] = frame["is_late"].astype(bool)
    return frame


def prepare(deliveries: pd.DataFrame) -> TrainingData:
    """Attach the point-in-time seller history and keep the modelling window."""
    deliveries = _normalize(deliveries).sort_values(["purchased_at", "order_id"], kind="stable")
    deliveries = deliveries.reset_index(drop=True)
    events = deliveries.rename(columns={"delivered_to_customer_at": "delivered_at"})
    history = point_in_time_history(deliveries, events)
    rows = pd.concat([deliveries, history], axis=1)
    in_window = (rows["purchased_at"] >= WINDOW_START) & (rows["purchased_at"] < WINDOW_END)
    return TrainingData(rows=rows[in_window].reset_index(drop=True), deliveries=events)


def load_from_postgres(conninfo: str) -> TrainingData:
    """Read the deliveries from the warehouse and prepare them."""
    import psycopg

    with psycopg.connect(conninfo) as conn:
        cursor = conn.execute(DELIVERIES_SQL)
        columns = [column.name for column in cursor.description]
        frame = pd.DataFrame(cursor.fetchall(), columns=columns)
    return prepare(frame)
