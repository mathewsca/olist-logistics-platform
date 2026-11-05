"""Order-level raw inputs from the items of a request, as the marts build them for training."""

import numpy as np
import pandas as pd

ORDER_KEY = "order_key"
# One row per unit sold, like the source's order_items: an item bought twice is two rows.
ORDER_ITEM_COLUMNS = (
    ORDER_KEY,
    "seller_id",
    "seller_zip_code_prefix",
    "seller_state",
    "price",
    "freight_value",
    "product_category",
    "product_weight_g",
    "product_length_cm",
    "product_height_cm",
    "product_width_cm",
)
DIMENSION_COLUMNS = ("product_length_cm", "product_height_cm", "product_width_cm")


def aggregate_items(items: pd.DataFrame) -> pd.DataFrame:
    """One row per ``order_key``, mirroring ``int_orders__items_summary`` and the training query.

    The main item (origin seller, category) is the most expensive one, ties broken by position,
    as ``order_item_id`` breaks them in dbt.
    """
    missing = [column for column in ORDER_ITEM_COLUMNS if column not in items.columns]
    if missing:
        raise ValueError(f"Missing item columns: {', '.join(missing)}")

    items = items.reset_index(drop=True)
    dimensions = items[list(DIMENSION_COLUMNS)].astype(float)
    items = items.assign(
        price=items["price"].astype(float),
        freight_value=items["freight_value"].astype(float),
        product_weight_g=items["product_weight_g"].astype(float),
        position=np.arange(len(items)),
        # Postgres: a product with any missing side has no volume, while greatest() skips nulls.
        volume_cm3=dimensions.prod(axis=1, skipna=False),
        max_side_cm=dimensions.max(axis=1),
    )

    grouped = items.groupby(ORDER_KEY, sort=False)
    summary = pd.DataFrame(
        {
            "item_count": grouped.size(),
            "seller_count": grouped["seller_id"].nunique(),
            "items_value": grouped["price"].sum(),
            "freight_value": grouped["freight_value"].sum(),
            # min_count=1: if every product lacks the attribute, NaN, as SQL sum() returns null.
            "total_weight_g": grouped["product_weight_g"].sum(min_count=1),
            "total_volume_cm3": grouped["volume_cm3"].sum(min_count=1),
            "max_side_cm": grouped["max_side_cm"].max(),
        }
    )
    main = (
        items.sort_values(
            [ORDER_KEY, "price", "position"], ascending=[True, False, True], kind="stable"
        )
        .drop_duplicates(ORDER_KEY)
        .set_index(ORDER_KEY)
    )
    summary["seller_id"] = main["seller_id"]
    summary["main_product_category"] = main["product_category"]
    summary["origin_zip_code_prefix"] = main["seller_zip_code_prefix"]
    summary["origin_state"] = main["seller_state"]
    return summary


def attach_coordinates(orders: pd.DataFrame, geography: pd.DataFrame) -> pd.DataFrame:
    """Add origin/destination latitude and longitude from a zip-prefix table (``dim_geography``).

    Prefixes missing from the table get NaN, as the left join in the training query does.
    """
    coordinates = geography[["latitude", "longitude"]].astype(float)
    result = orders.copy()
    for side in ("origin", "destination"):
        found = coordinates.reindex(orders[f"{side}_zip_code_prefix"].to_numpy())
        result[f"{side}_latitude"] = found["latitude"].to_numpy()
        result[f"{side}_longitude"] = found["longitude"].to_numpy()
    return result
