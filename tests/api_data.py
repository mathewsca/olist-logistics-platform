"""A small bundle fitted on synthetic orders, so API tests run without MLflow or the warehouse."""

import numpy as np
import pandas as pd

from olist_platform.api.bundle import ModelBundle
from olist_platform.features import build_features, history_snapshot
from olist_platform.models.estimators import classification_candidates, regression_candidates

STATES = ("SP", "RJ", "MG", "BA")
ZIPS = {"SP": "05849", "RJ": "22041", "MG": "30140", "BA": "40020"}
COORDINATES = {"SP": (-23.65, -46.75), "RJ": (-22.97, -43.19), "MG": (-19.92, -43.94),
               "BA": (-12.97, -38.50)}  # fmt: skip
KNOWN_SELLER = "6560211a19b47992c3666cc44a7e94c0"
THRESHOLD = 0.5


def synthetic_rows(rows: int = 400, seed: int = 3) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    origin = rng.choice(STATES, rows)
    destination = rng.choice(STATES, rows)
    purchased_at = pd.Timestamp("2017-03-01") + pd.to_timedelta(rng.integers(0, 400, rows), "D")
    promised = rng.integers(8, 40, rows)
    frame = pd.DataFrame(
        {
            "seller_id": rng.choice([KNOWN_SELLER, "s2", "s3"], rows),
            "purchased_at": purchased_at,
            "estimated_delivery_date": purchased_at.normalize() + pd.to_timedelta(promised, "D"),
            "items_value": rng.gamma(2.0, 60.0, rows),
            "freight_value": rng.gamma(2.0, 10.0, rows),
            "item_count": rng.integers(1, 4, rows),
            "seller_count": 1,
            "total_weight_g": rng.gamma(2.0, 800.0, rows),
            "total_volume_cm3": rng.gamma(2.0, 5000.0, rows),
            "max_side_cm": rng.uniform(10, 80, rows),
            "main_product_category": rng.choice(["bed_bath_table", "toys", "housewares"], rows),
            "origin_state": origin,
            "destination_state": destination,
            "origin_latitude": [COORDINATES[s][0] for s in origin],
            "origin_longitude": [COORDINATES[s][1] for s in origin],
            "destination_latitude": [COORDINATES[s][0] for s in destination],
            "destination_longitude": [COORDINATES[s][1] for s in destination],
            "seller_prior_deliveries": rng.integers(0, 50, rows).astype(float),
            "seller_prior_late_rate": rng.uniform(0, 0.2, rows),
            "seller_prior_mean_delivery_days": rng.uniform(5, 20, rows),
        }
    )
    frame["delivery_days"] = rng.uniform(3, 30, rows) + 5 * (origin != destination)
    frame["is_late"] = frame["delivery_days"] > promised
    frame["delivered_at"] = frame["purchased_at"] + pd.to_timedelta(frame["delivery_days"], "D")
    return frame


def fitted_bundle() -> ModelBundle:
    rows = synthetic_rows()
    features = build_features(rows)
    classifier = classification_candidates(float(rows["is_late"].mean()))[0].pipeline
    classifier.fit(features, rows["is_late"].astype(int))
    regressor = regression_candidates()[0].pipeline
    regressor.fit(features, rows["delivery_days"])
    geography = pd.DataFrame(
        {
            "latitude": [COORDINATES[s][0] for s in STATES],
            "longitude": [COORDINATES[s][1] for s in STATES],
        },
        index=pd.Index([ZIPS[s] for s in STATES], name="zip_code_prefix"),
    )
    metadata = {
        "classifier": {"name": "olist-late-delivery", "version": "1", "threshold": THRESHOLD,
                       "algorithm": "logistic_regression", "run_id": "c1"},
        "regressor": {"name": "olist-delivery-days", "version": "1",
                      "algorithm": "ridge_regression", "run_id": "r1"},
        "seller_history_as_of": "2018-09-01T00:00:00",
        "served_from": "export",
    }  # fmt: skip
    return ModelBundle(
        classifier=classifier,
        regressor=regressor,
        threshold=THRESHOLD,
        seller_history=history_snapshot(rows, pd.Timestamp("2018-09-01")),
        geography=geography,
        metadata=metadata,
    )
