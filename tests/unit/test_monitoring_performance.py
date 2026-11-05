import math

import numpy as np
import pandas as pd

from olist_platform.monitoring.performance import (
    GATE_MIN_POSITIVES,
    MonthPerformance,
    month_performance,
    quality_gate,
    region_slices,
    retrain_reasons,
)

VALIDATION = {"lift": 2.0, "mae": 5.0}


def performance(lift: float = 2.0, mae: float = 5.0) -> MonthPerformance:
    return MonthPerformance(
        orders=100, labelled=90, late_rate=0.1, pr_auc=lift * 0.1, lift=lift, recall=0.5,
        flagged_rate=0.1, mae=mae, bias=0.0,
    )  # fmt: skip


def test_month_performance_ignores_unlabelled_orders():
    is_late = pd.Series([True, False, False, True])
    labelled = pd.Series([True, True, True, False])
    scores = np.array([0.9, 0.2, 0.1, 0.0])
    result = month_performance(
        is_late, pd.Series([10.0, 5.0, 4.0, 99.0]), scores, np.array([9.0, 5.0, 4.0, 0.0]),
        threshold=0.5, labelled=labelled,
    )  # fmt: skip
    assert result.orders == 4
    assert result.labelled == 3
    assert math.isclose(result.late_rate, 1 / 3)
    assert result.pr_auc == 1.0
    assert result.recall == 1.0
    assert math.isclose(result.mae, 1 / 3)


def test_no_trigger_keeps_the_champion():
    assert retrain_reasons(0.1, performance(), VALIDATION) == []


def test_each_trigger_explains_itself():
    reasons = retrain_reasons(0.6, performance(lift=1.0, mae=7.0), VALIDATION)
    assert len(reasons) == 3
    assert reasons[0].startswith("data drift")
    assert "lift" in reasons[1]
    assert "MAE" in reasons[2]


def test_lift_exactly_at_the_trigger_does_not_retrain():
    assert retrain_reasons(0.0, performance(lift=1.5), VALIDATION) == []


def _gate_inputs(positives: int = GATE_MIN_POSITIVES):
    rng = np.random.default_rng(0)
    target = np.zeros(400, dtype=int)
    target[:positives] = 1
    days = rng.uniform(5, 20, 400)
    noisy = rng.uniform(size=400)
    sharp = np.where(target == 1, 0.7, 0.3) + rng.uniform(-0.25, 0.25, 400)
    return target, days, noisy, sharp


def test_gate_promotes_a_clearly_better_challenger():
    target, days, noisy, sharp = _gate_inputs()
    result = quality_gate(target, days, champion=(noisy, days + 3), challenger=(sharp, days + 1),
                          route_rule_scores=noisy)  # fmt: skip
    assert result.passed
    assert result.reasons == []


def test_gate_rejects_a_worse_mae_even_with_better_ranking():
    target, days, noisy, sharp = _gate_inputs()
    result = quality_gate(target, days, champion=(noisy, days), challenger=(sharp, days + 2),
                          route_rule_scores=noisy)  # fmt: skip
    assert not result.passed
    assert any("MAE" in reason for reason in result.reasons)


def test_gate_rejects_a_challenger_that_does_not_beat_the_route_rule():
    target, days, noisy, sharp = _gate_inputs()
    result = quality_gate(target, days, champion=(noisy, days), challenger=(sharp, days),
                          route_rule_scores=sharp)  # fmt: skip
    assert not result.passed
    assert any("route rule" in reason for reason in result.reasons)


def test_gate_needs_enough_late_orders_to_decide():
    target, days, noisy, sharp = _gate_inputs(positives=GATE_MIN_POSITIVES - 1)
    result = quality_gate(target, days, champion=(noisy, days), challenger=(sharp, days),
                          route_rule_scores=noisy)  # fmt: skip
    assert not result.passed
    assert result.reasons[0].startswith(f"only {GATE_MIN_POSITIVES - 1} late orders")


def test_region_slices_hide_ranking_metrics_with_few_late_orders():
    regions = pd.Series(["Sudeste"] * 50 + ["Norte"] * 5)
    is_late = pd.Series([True] * 12 + [False] * 38 + [True] + [False] * 4)
    scores = np.linspace(1, 0, 55)
    slices = region_slices(regions, is_late, scores, 0.5, pd.Series([True] * 55)).set_index(
        "region"
    )
    assert slices.loc["Sudeste", "orders"] == 50
    assert not math.isnan(slices.loc["Sudeste", "pr_auc"])
    assert math.isnan(slices.loc["Norte", "pr_auc"])
    assert math.isnan(slices.loc["Norte", "recall"])


def test_a_month_without_labels_gives_missing_metrics():
    result = month_performance(
        pd.Series([True, False]), pd.Series([10.0, 5.0]), np.array([0.9, 0.1]),
        np.array([9.0, 5.0]), threshold=0.5, labelled=pd.Series([False, False]),
    )  # fmt: skip
    assert result.orders == 2
    assert result.labelled == 0
    assert math.isnan(result.mae)
    assert math.isnan(result.pr_auc)
