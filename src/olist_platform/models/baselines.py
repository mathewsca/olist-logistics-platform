"""Reference rules every model has to beat, fit on the training period only."""

import numpy as np
import pandas as pd

ROUTE_KEYS = ["origin_state", "destination_state"]
# Routes with fewer training deliveries fall back to the overall median.
MIN_ROUTE_DELIVERIES = 30


class MajorityClass:
    """Always 'on time', i.e. taking the Olist promise at face value; scores are the train rate."""

    def fit(self, features: pd.DataFrame, target: pd.Series) -> "MajorityClass":
        self.rate_ = float(np.mean(target))
        return self

    def score(self, features: pd.DataFrame) -> np.ndarray:
        """Constant late probability."""
        return np.full(len(features), self.rate_)


class RouteMedian:
    """Median delivery days of the order's state-to-state route in the training period."""

    def fit(self, features: pd.DataFrame, delivery_days: pd.Series) -> "RouteMedian":
        frame = features[ROUTE_KEYS].assign(days=np.asarray(delivery_days, dtype=float))
        grouped = frame.groupby(ROUTE_KEYS)["days"].agg(["median", "size"])
        self.routes_ = grouped.loc[grouped["size"] >= MIN_ROUTE_DELIVERIES, "median"]
        self.overall_ = float(frame["days"].median())
        return self

    def predict(self, features: pd.DataFrame) -> np.ndarray:
        """Expected delivery days."""
        keys = pd.MultiIndex.from_frame(features[ROUTE_KEYS].astype(object))
        return self.routes_.reindex(keys).fillna(self.overall_).to_numpy(dtype=float)


class RouteSlack(RouteMedian):
    """Lateness score: how many days the typical delivery on the route exceeds the promise."""

    def score(self, features: pd.DataFrame) -> np.ndarray:
        """Route median minus promised days (higher means more likely late)."""
        return self.predict(features) - features["estimated_delivery_days"].to_numpy(dtype=float)


class OlistEstimate:
    """The promise itself as the delivery time forecast."""

    def fit(self, features: pd.DataFrame, delivery_days: pd.Series) -> "OlistEstimate":
        return self

    def predict(self, features: pd.DataFrame) -> np.ndarray:
        """Promised days."""
        return features["estimated_delivery_days"].to_numpy(dtype=float)


class TrainMedian:
    """Median delivery days of the training period."""

    def fit(self, features: pd.DataFrame, delivery_days: pd.Series) -> "TrainMedian":
        self.median_ = float(np.median(delivery_days))
        return self

    def predict(self, features: pd.DataFrame) -> np.ndarray:
        """Constant forecast."""
        return np.full(len(features), self.median_)
