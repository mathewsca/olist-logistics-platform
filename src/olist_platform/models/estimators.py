"""Candidate models as scikit-learn pipelines over ``build_features`` output."""

from dataclasses import dataclass, field
from typing import Any

import numpy as np
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.pipeline import Pipeline, make_pipeline
from sklearn.preprocessing import FunctionTransformer, OneHotEncoder, OrdinalEncoder, StandardScaler

from olist_platform.features import CATEGORICAL_FEATURES, NUMERIC_FEATURES

RANDOM_STATE = 42

# Long right tails (money, weight, distance): linear models fit their logarithm much better.
SKEWED_FEATURES = (
    "distance_km",
    "km_per_estimated_day",
    "items_value",
    "freight_value",
    "freight_ratio",
    "total_weight_g",
    "total_volume_cm3",
    "seller_prior_deliveries",
)

LIGHTGBM_PARAMS: dict[str, Any] = {
    "n_estimators": 400,
    "learning_rate": 0.05,
    "num_leaves": 31,
    "min_child_samples": 50,
    "subsample": 0.8,
    "subsample_freq": 1,
    "colsample_bytree": 0.8,
    "reg_lambda": 1.0,
    "random_state": RANDOM_STATE,
    "verbose": -1,
}


@dataclass(frozen=True)
class Candidate:
    """A named pipeline and the extra arguments its ``fit`` needs."""

    name: str
    pipeline: Pipeline
    fit_params: dict[str, Any] = field(default_factory=dict)
    is_tree: bool = False


def _linear_preprocessor() -> ColumnTransformer:
    skewed = [c for c in NUMERIC_FEATURES if c in SKEWED_FEATURES]
    plain = [c for c in NUMERIC_FEATURES if c not in SKEWED_FEATURES]
    numeric = make_pipeline(SimpleImputer(strategy="median", add_indicator=True), StandardScaler())
    log_numeric = make_pipeline(
        SimpleImputer(strategy="median", add_indicator=True),
        FunctionTransformer(np.log1p, feature_names_out="one-to-one"),
        StandardScaler(),
    )
    categorical = make_pipeline(
        SimpleImputer(strategy="constant", fill_value="unknown"),
        OneHotEncoder(handle_unknown="infrequent_if_exist", min_frequency=30),
    )
    return ColumnTransformer(
        [
            ("numeric", numeric, plain),
            ("log_numeric", log_numeric, skewed),
            ("categorical", categorical, list(CATEGORICAL_FEATURES)),
        ]
    )


def _tree_preprocessor() -> ColumnTransformer:
    # Unseen or missing categories become -1, which LightGBM treats as missing.
    encoder = OrdinalEncoder(
        handle_unknown="use_encoded_value",
        unknown_value=-1,
        encoded_missing_value=-1,
        min_frequency=30,
    )
    return ColumnTransformer(
        [
            ("numeric", "passthrough", list(NUMERIC_FEATURES)),
            ("categorical", encoder, list(CATEGORICAL_FEATURES)),
        ],
        verbose_feature_names_out=False,
    ).set_output(transform="pandas")


def _lightgbm_fit_params() -> dict[str, Any]:
    return {"model__categorical_feature": list(CATEGORICAL_FEATURES)}


def classification_candidates(positive_rate: float) -> list[Candidate]:
    """Logistic regression and LightGBM, with and without reweighting the rare late class."""
    from lightgbm import LGBMClassifier

    if not 0 < positive_rate < 1:
        raise ValueError(f"Training period needs both classes; late rate is {positive_rate:.3f}")
    negatives_per_positive = (1 - positive_rate) / positive_rate
    return [
        Candidate(
            "logistic_regression",
            Pipeline(
                [
                    ("features", _linear_preprocessor()),
                    (
                        "model",
                        LogisticRegression(
                            class_weight="balanced", max_iter=2000, random_state=RANDOM_STATE
                        ),
                    ),
                ]
            ),
        ),
        Candidate(
            "lightgbm",
            Pipeline(
                [("features", _tree_preprocessor()), ("model", LGBMClassifier(**LIGHTGBM_PARAMS))]
            ),
            _lightgbm_fit_params(),
            is_tree=True,
        ),
        Candidate(
            "lightgbm_weighted",
            Pipeline(
                [
                    ("features", _tree_preprocessor()),
                    (
                        "model",
                        LGBMClassifier(**LIGHTGBM_PARAMS, scale_pos_weight=negatives_per_positive),
                    ),
                ]
            ),
            _lightgbm_fit_params(),
            is_tree=True,
        ),
    ]


def regression_candidates() -> list[Candidate]:
    """Ridge regression and LightGBM for the delivery time in days."""
    from lightgbm import LGBMRegressor

    return [
        Candidate(
            "ridge_regression",
            Pipeline([("features", _linear_preprocessor()), ("model", Ridge(alpha=1.0))]),
        ),
        Candidate(
            "lightgbm",
            Pipeline(
                [("features", _tree_preprocessor()), ("model", LGBMRegressor(**LIGHTGBM_PARAMS))]
            ),
            _lightgbm_fit_params(),
            is_tree=True,
        ),
    ]
