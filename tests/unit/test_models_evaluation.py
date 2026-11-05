import numpy as np
import pandas as pd
import pytest

from olist_platform.models.baselines import (
    MIN_ROUTE_DELIVERIES,
    MajorityClass,
    OlistEstimate,
    RouteMedian,
    RouteSlack,
    TrainMedian,
)
from olist_platform.models.evaluation import (
    best_f1_threshold,
    classification_metrics,
    regression_metrics,
)
from olist_platform.models.split import temporal_split


def test_temporal_split_is_ordered_and_disjoint():
    rows = pd.DataFrame(
        {
            "purchased_at": pd.to_datetime(
                ["2018-03-31 23:59", "2018-04-01 00:00", "2018-05-31 00:00", "2018-06-01 00:00"]
            ),
            "is_late": [False, True, False, True],
        }
    )
    split = temporal_split(rows)
    assert len(split.train) == len(split.validation) - 1 == len(split.test) == 1
    assert split.train["purchased_at"].max() < split.validation["purchased_at"].min()
    assert split.validation["purchased_at"].max() < split.test["purchased_at"].min()


def test_temporal_split_rejects_inverted_boundaries():
    with pytest.raises(ValueError):
        temporal_split(
            pd.DataFrame({"purchased_at": []}),
            pd.Timestamp("2018-06-01"),
            pd.Timestamp("2018-04-01"),
        )


def test_best_f1_threshold_separates_perfect_scores():
    target = np.array([0, 0, 1, 1])
    threshold = best_f1_threshold(target, np.array([0.1, 0.2, 0.8, 0.9]))
    assert threshold == pytest.approx(0.8)


def test_classification_metrics_at_threshold():
    metrics = classification_metrics(
        np.array([0, 1, 1, 0]), np.array([0.1, 0.9, 0.4, 0.6]), 0.5, is_probability=True
    )
    assert metrics["precision"] == pytest.approx(0.5)
    assert metrics["recall"] == pytest.approx(0.5)
    assert metrics["flagged_rate"] == pytest.approx(0.5)
    assert 0 < metrics["brier"] < 1


def test_score_baseline_has_no_brier():
    metrics = classification_metrics(
        np.array([0, 1]), np.array([-3.0, 2.0]), 0.0, is_probability=False
    )
    assert np.isnan(metrics["brier"])


def test_majority_class_never_flags_and_scores_the_train_rate():
    baseline = MajorityClass().fit(pd.DataFrame(index=range(4)), pd.Series([0, 0, 0, 1]))
    scores = baseline.score(pd.DataFrame(index=range(3)))
    assert list(scores) == [0.25] * 3
    metrics = classification_metrics(np.array([0, 1, 0]), scores, np.inf, is_probability=True)
    assert metrics["flagged_rate"] == 0
    assert metrics["pr_auc"] == pytest.approx(1 / 3)


def route_frame(routes):
    return pd.DataFrame(
        {
            "origin_state": [r[0] for r in routes],
            "destination_state": [r[1] for r in routes],
            "estimated_delivery_days": [20.0] * len(routes),
        }
    )


def test_route_median_falls_back_on_rare_routes():
    routes = [("SP", "SP")] * MIN_ROUTE_DELIVERIES + [("SP", "AM")]
    days = [5.0] * MIN_ROUTE_DELIVERIES + [40.0]
    baseline = RouteMedian().fit(route_frame(routes), pd.Series(days))
    predicted = baseline.predict(route_frame([("SP", "SP"), ("SP", "AM"), ("RR", "AC")]))
    assert list(predicted) == [5.0, 5.0, 5.0]


def test_route_slack_is_route_median_minus_promise():
    routes = [("SP", "RJ")] * MIN_ROUTE_DELIVERIES
    baseline = RouteSlack().fit(route_frame(routes), pd.Series([25.0] * MIN_ROUTE_DELIVERIES))
    assert baseline.score(route_frame([("SP", "RJ")]))[0] == pytest.approx(5.0)


def test_regression_baselines_and_metrics():
    frame = route_frame([("SP", "SP")] * 3)
    assert list(OlistEstimate().fit(frame, None).predict(frame)) == [20.0] * 3
    assert list(TrainMedian().fit(frame, pd.Series([1.0, 2.0, 9.0])).predict(frame)) == [2.0] * 3
    metrics = regression_metrics(np.array([10.0, 20.0]), np.array([12.0, 18.0]))
    assert metrics == pytest.approx({"mae": 2.0, "rmse": 2.0, "bias": 0.0})
