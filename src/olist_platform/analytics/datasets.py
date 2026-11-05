"""Tables the dashboard reads, from the warehouse marts or from a Parquet extract of them."""

import os
from collections.abc import Callable
from decimal import Decimal
from pathlib import Path

import pandas as pd

from olist_platform.analytics.quality import load_data_quality

DEFAULT_EXTRACT_DIR = Path("data/extract")

DATASETS: dict[str, str] = {
    "deliveries": """
        select
            deliveries.order_id,
            deliveries.seller_id,
            customers.customer_unique_id,
            deliveries.purchased_at,
            deliveries.approved_at,
            deliveries.delivered_to_customer_at,
            deliveries.delivery_days,
            deliveries.estimated_delivery_days,
            deliveries.delay_days,
            deliveries.is_late,
            deliveries.seller_handling_days,
            deliveries.carrier_transit_days,
            deliveries.origin_state,
            deliveries.origin_region,
            deliveries.destination_state,
            deliveries.destination_region,
            deliveries.is_same_state,
            deliveries.distance_km,
            deliveries.main_product_category,
            deliveries.item_count,
            deliveries.items_value,
            deliveries.freight_value,
            deliveries.is_multi_seller,
            deliveries.review_score,
            orders.main_payment_type,
            orders.review_mentions_delivery
        from marts.fct_deliveries as deliveries
        inner join marts.dim_customers as customers
            on deliveries.customer_id = customers.customer_id
        inner join marts.fct_orders as orders
            on deliveries.order_id = orders.order_id
    """,
    "orders": """
        select order_id, customer_unique_id, order_status, purchased_at
        from marts.fct_orders
    """,
    "state_centroids": """
        select state, avg(latitude) as latitude, avg(longitude) as longitude
        from marts.dim_geography
        group by state
    """,
}

# Written by `make monitor` and `make dbt-build`; the dashboard still opens without them.
OPTIONAL_DATASETS: dict[str, str | Callable] = {
    "data_quality": load_data_quality,
    "monitoring_runs": """
        select
            month, champion_version, orders, labelled, late_rate, pr_auc, lift, validation_lift,
            recall, flagged_rate, mae, validation_mae, drift_share, drifted_features,
            retrain_reasons, challenger_version, gate_passed, gate_detail
        from ml.monitoring_runs
        order by month
    """,
}

DATETIME_COLUMNS = {"purchased_at", "approved_at", "delivered_to_customer_at", "month"}
# Nullable in the marts, so they become pandas nullable types instead of float NaN / object.
NULLABLE_INT_COLUMNS = {"review_score"}
NULLABLE_BOOL_COLUMNS = {"review_mentions_delivery"}


def normalize(frame: pd.DataFrame) -> pd.DataFrame:
    """Same dtypes whatever the source: floats for numerics, datetimes for timestamps."""
    frame = frame.copy()
    for column in frame.columns:
        values = frame[column].dropna()
        if column in DATETIME_COLUMNS:
            frame[column] = pd.to_datetime(frame[column])
        elif column in NULLABLE_INT_COLUMNS:
            frame[column] = frame[column].astype("Int64")
        elif column in NULLABLE_BOOL_COLUMNS:
            frame[column] = frame[column].astype("boolean")
        elif not values.empty and isinstance(values.iloc[0], Decimal):
            frame[column] = frame[column].astype(float)
    return frame


def load_from_postgres(conninfo: str) -> dict[str, pd.DataFrame]:
    """Read every dataset from the warehouse."""
    import psycopg

    def read(conn, sql: str) -> pd.DataFrame:
        cursor = conn.execute(sql)
        columns = [column.name for column in cursor.description]
        return normalize(pd.DataFrame(cursor.fetchall(), columns=columns))

    frames = {}
    with psycopg.connect(conninfo, autocommit=True) as conn:
        for name, sql in DATASETS.items():
            frames[name] = read(conn, sql)
        for name, source in OPTIONAL_DATASETS.items():
            try:
                frames[name] = source(conn) if callable(source) else read(conn, source)
            except psycopg.errors.UndefinedTable:
                frames[name] = pd.DataFrame()
    return frames


def parquet_path(location: str, name: str) -> str:
    """Path or URL of one dataset inside an extract (a local directory or a base URL)."""
    return f"{location.rstrip('/')}/{name}.parquet"


def load_from_parquet(location: str) -> dict[str, pd.DataFrame]:
    """Read every dataset from a Parquet extract (local directory or base URL)."""
    frames = {name: pd.read_parquet(parquet_path(location, name)) for name in DATASETS}
    for name in OPTIONAL_DATASETS:
        try:
            frames[name] = pd.read_parquet(parquet_path(location, name))
        except (FileNotFoundError, OSError):
            frames[name] = pd.DataFrame()
    return frames


def export_parquet(frames: dict[str, pd.DataFrame], directory: Path) -> list[Path]:
    """Write one Parquet file per dataset."""
    directory.mkdir(parents=True, exist_ok=True)
    paths = []
    for name, frame in frames.items():
        if frame.empty and name in OPTIONAL_DATASETS:
            continue
        path = directory / f"{name}.parquet"
        frame.to_parquet(path, index=False)
        paths.append(path)
    return paths


def load_datasets() -> dict[str, pd.DataFrame]:
    """Datasets from the source chosen by ``DASHBOARD_SOURCE`` (``postgres`` or ``parquet``)."""
    source = os.environ.get("DASHBOARD_SOURCE", "postgres")
    if source == "parquet":
        location = os.environ.get("DASHBOARD_PARQUET_LOCATION", str(DEFAULT_EXTRACT_DIR))
        return load_from_parquet(location)
    if source == "postgres":
        from olist_platform.ingestion.settings import WarehouseSettings

        return load_from_postgres(WarehouseSettings.from_env().conninfo())
    raise ValueError(f"DASHBOARD_SOURCE must be 'postgres' or 'parquet', got {source!r}")
