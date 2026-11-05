"""Synthetic deliveries shaped like ``fct_deliveries``, for training and monitoring tests."""

import numpy as np
import pandas as pd

STATES = ["SP", "RJ", "MG", "BA", "RS"]
COORDINATES = {
    "SP": (-23.5, -46.6),
    "RJ": (-22.9, -43.2),
    "MG": (-19.9, -43.9),
    "BA": (-12.9, -38.5),
    "RS": (-30.0, -51.2),
}
REGIONS = {"SP": "Sudeste", "RJ": "Sudeste", "MG": "Sudeste", "BA": "Nordeste", "RS": "Sul"}


def synthetic_deliveries(rows: int = 2400, seed: int = 7) -> pd.DataFrame:
    """Deliveries whose lateness depends on distance and promise, like the real data."""
    rng = np.random.default_rng(seed)
    purchased_at = pd.Timestamp("2016-12-01") + pd.to_timedelta(
        np.sort(rng.uniform(0, 640, rows)), unit="D"
    )
    origin = rng.choice(STATES, rows)
    destination = rng.choice(STATES, rows)
    estimated_days = rng.integers(8, 35, rows)
    far = origin != destination
    delivery_days = rng.gamma(3, 3, rows) + np.where(far, 6, 0)
    delivered_at = purchased_at + pd.to_timedelta(delivery_days, unit="D")
    estimated = purchased_at.normalize() + pd.to_timedelta(estimated_days, unit="D")
    return pd.DataFrame(
        {
            "order_id": [f"o{i}" for i in range(rows)],
            "seller_id": rng.choice([f"s{i}" for i in range(40)], rows),
            "purchased_at": purchased_at,
            "estimated_delivery_date": estimated,
            "delivered_to_customer_at": delivered_at,
            "is_late": delivered_at.normalize() > estimated,
            "delivery_days": delivery_days,
            "items_value": rng.gamma(2, 60, rows),
            "freight_value": rng.gamma(2, 10, rows),
            "item_count": rng.integers(1, 4, rows),
            "seller_count": 1,
            "main_product_category": rng.choice(["toys", "health_beauty", "bed_bath_table"], rows),
            "origin_state": origin,
            "destination_state": destination,
            "destination_region": [REGIONS[s] for s in destination],
            "origin_latitude": [COORDINATES[s][0] for s in origin],
            "origin_longitude": [COORDINATES[s][1] for s in origin],
            "destination_latitude": [COORDINATES[s][0] for s in destination],
            "destination_longitude": [COORDINATES[s][1] for s in destination],
            "total_weight_g": rng.integers(100, 9000, rows),
            "total_volume_cm3": rng.integers(500, 40000, rows),
            "max_side_cm": rng.integers(10, 80, rows),
        }
    )
