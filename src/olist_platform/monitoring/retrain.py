"""Fit the champion pair (classifier + regressor) from what was known at a simulated date."""

from dataclasses import dataclass

import numpy as np
import pandas as pd

from olist_platform.features import (
    SELLER_HISTORY_COLUMNS,
    build_features,
    history_snapshot,
    lookup_history,
)
from olist_platform.models.baselines import RouteSlack
from olist_platform.models.data import TrainingData
from olist_platform.models.estimators import classification_candidates, regression_candidates
from olist_platform.models.evaluation import (
    best_f1_threshold,
    classification_metrics,
    regression_metrics,
)
from olist_platform.monitoring.windows import FitWindow


@dataclass
class ModelPair:
    """What production serves at a point in time, plus what monitoring compares against."""

    classifier: object
    regressor: object
    threshold: float
    seller_history: pd.DataFrame
    window: FitWindow
    classifier_name: str
    regressor_name: str
    validation: dict[str, float]
    reference: pd.DataFrame
    route_rule: RouteSlack | None = None


def known_rows(data: TrainingData, window: FitWindow) -> pd.DataFrame:
    """Orders bought before ``data_end`` whose delivery was already known at ``label_cutoff``.

    Filtering on purchase date alone would read labels that did not exist yet.
    """
    rows = data.rows
    return rows[
        (rows["purchased_at"] < window.data_end)
        & (rows["delivered_to_customer_at"] < window.label_cutoff)
    ]


def _select_classifier(train, validation, features):
    rate = float(train["is_late"].mean())
    best = None
    for candidate in classification_candidates(rate):
        candidate.pipeline.fit(
            features["train"], train["is_late"].astype(int), **candidate.fit_params
        )
        scores = candidate.pipeline.predict_proba(features["validation"])[:, 1]
        threshold = best_f1_threshold(validation["is_late"].astype(int), scores)
        metrics = classification_metrics(
            validation["is_late"].astype(int), scores, threshold, is_probability=True
        )
        if best is None or metrics["pr_auc"] > best[2]["pr_auc"]:
            best = (candidate, threshold, metrics)
    return best


def _select_regressor(train, validation, features):
    best = None
    for candidate in regression_candidates():
        candidate.pipeline.fit(features["train"], train["delivery_days"], **candidate.fit_params)
        metrics = regression_metrics(
            validation["delivery_days"], candidate.pipeline.predict(features["validation"])
        )
        if best is None or metrics["mae"] < best[1]["mae"]:
            best = (candidate, metrics)
    return best


def fit_pair(data: TrainingData, window: FitWindow) -> ModelPair:
    """Same candidates and selection rules as ``make train``, on what was known at the cutoff."""
    rows = known_rows(data, window)
    train = rows[rows["purchased_at"] < window.validation_start]
    validation = rows[rows["purchased_at"] >= window.validation_start]
    if train.empty or validation["is_late"].sum() == 0:
        raise ValueError(f"Not enough labelled data to fit at {window}")
    features = {"train": build_features(train), "validation": build_features(validation)}

    classifier, threshold, class_metrics = _select_classifier(train, validation, features)
    regressor, reg_metrics = _select_regressor(train, validation, features)
    late_rate = float(validation["is_late"].mean())
    route_rule = RouteSlack().fit(features["train"], train["delivery_days"])
    return ModelPair(
        classifier=classifier.pipeline,
        regressor=regressor.pipeline,
        threshold=threshold,
        seller_history=history_snapshot(data.deliveries, window.label_cutoff),
        window=window,
        classifier_name=classifier.name,
        regressor_name=regressor.name,
        validation={
            "pr_auc": class_metrics["pr_auc"],
            "late_rate": late_rate,
            "lift": class_metrics["pr_auc"] / late_rate,
            "recall": class_metrics["recall"],
            "mae": reg_metrics["mae"],
        },
        reference=features["train"],
        route_rule=route_rule,
    )


def serving_features(rows: pd.DataFrame, pair: ModelPair) -> pd.DataFrame:
    """Features as the API would build them: seller history from the pair's frozen snapshot."""
    served = rows.drop(columns=list(SELLER_HISTORY_COLUMNS))
    history = lookup_history(rows["seller_id"].astype(str), pair.seller_history)
    return build_features(pd.concat([served, history], axis=1))


def score(pair: ModelPair, features: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """Late-delivery scores and delivery days (clipped at 0, like the API)."""
    scores = pair.classifier.predict_proba(features)[:, 1]
    days = np.clip(np.asarray(pair.regressor.predict(features), dtype=float), 0, None)
    return scores, days
