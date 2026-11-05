"""Feature engineering shared between training and inference."""

from olist_platform.features.build import (
    CATEGORICAL_FEATURES,
    FEATURE_COLUMNS,
    NUMERIC_FEATURES,
    RAW_INPUT_COLUMNS,
    build_features,
)
from olist_platform.features.order_input import (
    ORDER_ITEM_COLUMNS,
    ORDER_KEY,
    aggregate_items,
    attach_coordinates,
)
from olist_platform.features.seller_history import (
    SELLER_HISTORY_COLUMNS,
    history_snapshot,
    lookup_history,
    point_in_time_history,
)

__all__ = [
    "CATEGORICAL_FEATURES",
    "FEATURE_COLUMNS",
    "NUMERIC_FEATURES",
    "ORDER_ITEM_COLUMNS",
    "ORDER_KEY",
    "RAW_INPUT_COLUMNS",
    "SELLER_HISTORY_COLUMNS",
    "aggregate_items",
    "attach_coordinates",
    "build_features",
    "history_snapshot",
    "lookup_history",
    "point_in_time_history",
]
