"""Score orders with a bundle; every feature comes from ``olist_platform.features``."""

import numpy as np
import pandas as pd

from olist_platform.api.bundle import ModelBundle
from olist_platform.api.schemas import OrderRequest, Prediction
from olist_platform.features import (
    ORDER_KEY,
    aggregate_items,
    attach_coordinates,
    build_features,
    lookup_history,
)


def items_frame(orders: list[OrderRequest]) -> pd.DataFrame:
    """One row per unit, the grain of the source's order items."""
    rows = [
        {
            ORDER_KEY: key,
            "seller_id": item.seller_id,
            "seller_zip_code_prefix": item.seller_zip_code,
            "seller_state": item.seller_state,
            "price": item.price,
            "freight_value": item.freight_value,
            "product_category": item.product_category,
            "product_weight_g": item.product_weight_g,
            "product_length_cm": item.product_length_cm,
            "product_height_cm": item.product_height_cm,
            "product_width_cm": item.product_width_cm,
        }
        for key, order in enumerate(orders)
        for item in order.items
        for _ in range(item.quantity)
    ]
    frame = pd.DataFrame(rows)
    numeric = [c for c in frame.columns if c.startswith("product_") and c != "product_category"]
    frame[numeric] = frame[numeric].astype(float)
    return frame


def raw_inputs(orders: list[OrderRequest], bundle: ModelBundle) -> pd.DataFrame:
    """The training query's columns, rebuilt from the request and the bundle's lookups."""
    summary = aggregate_items(items_frame(orders))
    summary["purchased_at"] = [order.local_purchase_time() for order in orders]
    summary["estimated_delivery_date"] = [
        pd.Timestamp(order.estimated_delivery_date) for order in orders
    ]
    summary["destination_zip_code_prefix"] = [order.customer_zip_code for order in orders]
    summary["destination_state"] = [order.customer_state for order in orders]
    summary = attach_coordinates(summary, bundle.geography)
    history = lookup_history(summary["seller_id"].astype(str), bundle.seller_history)
    return pd.concat([summary, history], axis=1)


def _warnings(raw: pd.DataFrame, bundle: ModelBundle) -> list[list[str]]:
    checks = [
        (
            ~raw["seller_id"].isin(bundle.seller_history.index),
            "seller without delivery history: platform averages used",
        ),
        (raw["origin_latitude"].isna(), "origin zip prefix without coordinates: distance unknown"),
        (
            raw["destination_latitude"].isna(),
            "destination zip prefix without coordinates: distance unknown",
        ),
    ]
    as_of = bundle.metadata.get("seller_history_as_of")
    if as_of:
        # The snapshot already counts deliveries made after such a purchase (even this order's own),
        # so replaying past orders through the API leaks the future.
        checks.append(
            (
                raw["purchased_at"] < pd.Timestamp(as_of),
                f"purchase before the seller-history snapshot ({as_of}): history includes later "
                "deliveries",
            )
        )
    flags = np.column_stack([mask.to_numpy(dtype=bool) for mask, _ in checks])
    messages = [message for _, message in checks]
    return [[messages[i] for i in np.flatnonzero(row)] for row in flags]


def predict(orders: list[OrderRequest], bundle: ModelBundle) -> list[Prediction]:
    """Late-delivery risk and delivery days for each order, in request order."""
    raw = raw_inputs(orders, bundle)
    features = build_features(raw)
    scores = bundle.classifier.predict_proba(features)[:, 1]
    # A linear champion can extrapolate below zero; a delivery cannot precede the purchase.
    days = np.clip(np.asarray(bundle.regressor.predict(features), dtype=float), 0, None)
    delivery_dates = raw["purchased_at"] + pd.to_timedelta(days, unit="D")
    promised = features["estimated_delivery_days"].to_numpy()
    warnings = _warnings(raw, bundle)
    return [
        Prediction(
            late_risk_score=float(scores[i]),
            is_late_predicted=bool(scores[i] >= bundle.threshold),
            late_threshold=bundle.threshold,
            predicted_delivery_days=round(float(days[i]), 2),
            predicted_delivery_date=delivery_dates.iloc[i].date(),
            promised_delivery_days=int(promised[i]),
            warnings=warnings[i],
        )
        for i in range(len(orders))
    ]
