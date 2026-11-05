"""Monthly performance, retraining triggers and the quality gate (thresholds fixed upfront)."""

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score

from olist_platform.models.evaluation import regression_metrics

# Set before the first simulation run, never tuned on its results.
DRIFT_SHARE_TRIGGER = 0.5
LIFT_DROP_TRIGGER = 0.25
MAE_RISE_TRIGGER = 0.25
GATE_MIN_RELATIVE_GAIN = 0.05
# Below this, PR-AUC on one month is too noisy to rank two models.
GATE_MIN_POSITIVES = 30
SLICE_MIN_POSITIVES = 10


@dataclass(frozen=True)
class MonthPerformance:
    """Champion metrics on one month's matured labels."""

    orders: int
    labelled: int
    late_rate: float
    pr_auc: float
    lift: float
    recall: float
    flagged_rate: float
    mae: float
    bias: float


def month_performance(
    is_late: pd.Series, delivery_days: pd.Series, scores: np.ndarray, days: np.ndarray,
    threshold: float, labelled: pd.Series,
) -> MonthPerformance:  # fmt: skip
    """Metrics on the labelled orders; unlabelled ones only count in ``orders``."""
    mask = labelled.to_numpy(dtype=bool)
    target = is_late.to_numpy(dtype=int)[mask]
    flagged = scores[mask] >= threshold
    late_rate = float(target.mean()) if mask.any() else float("nan")
    pr_auc = float(average_precision_score(target, scores[mask])) if target.any() else float("nan")
    regression = (
        regression_metrics(delivery_days.to_numpy()[mask], days[mask])
        if mask.any()
        else {"mae": float("nan"), "bias": float("nan")}
    )
    return MonthPerformance(
        orders=len(is_late),
        labelled=int(mask.sum()),
        late_rate=late_rate,
        pr_auc=pr_auc,
        lift=pr_auc / late_rate if late_rate else float("nan"),
        recall=float(flagged[target == 1].mean()) if target.any() else float("nan"),
        flagged_rate=float(flagged.mean()),
        mae=regression["mae"],
        bias=regression["bias"],
    )


def retrain_reasons(
    drift_share: float, performance: MonthPerformance, validation: dict[str, float]
) -> list[str]:
    """Why the champion should be retrained; empty means keep it."""
    reasons = []
    if drift_share >= DRIFT_SHARE_TRIGGER:
        reasons.append(f"data drift in {drift_share:.0%} of the features")
    if performance.lift < (1 - LIFT_DROP_TRIGGER) * validation["lift"]:
        reasons.append(
            f"PR-AUC lift {performance.lift:.2f} vs {validation['lift']:.2f} on validation"
        )
    if performance.mae > (1 + MAE_RISE_TRIGGER) * validation["mae"]:
        reasons.append(f"MAE {performance.mae:.2f} vs {validation['mae']:.2f} on validation")
    return reasons


@dataclass(frozen=True)
class GateResult:
    """Champion vs challenger on the held-out month."""

    passed: bool
    reasons: list[str]
    champion_pr_auc: float
    challenger_pr_auc: float
    route_rule_pr_auc: float
    champion_mae: float
    challenger_mae: float


def quality_gate(
    target: np.ndarray, delivery_days: np.ndarray, champion: tuple[np.ndarray, np.ndarray],
    challenger: tuple[np.ndarray, np.ndarray], route_rule_scores: np.ndarray,
) -> GateResult:  # fmt: skip
    """Promote only a challenger that beats the champion and the route rule without a worse MAE."""
    target = np.asarray(target, dtype=int)
    champion_pr_auc = float(average_precision_score(target, champion[0]))
    challenger_pr_auc = float(average_precision_score(target, challenger[0]))
    route_pr_auc = float(average_precision_score(target, route_rule_scores))
    champion_mae = regression_metrics(delivery_days, champion[1])["mae"]
    challenger_mae = regression_metrics(delivery_days, challenger[1])["mae"]

    failures = []
    if target.sum() < GATE_MIN_POSITIVES:
        failures.append(f"only {int(target.sum())} late orders in the held-out month")
    if challenger_pr_auc < (1 + GATE_MIN_RELATIVE_GAIN) * champion_pr_auc:
        failures.append(
            f"PR-AUC {challenger_pr_auc:.3f} not {GATE_MIN_RELATIVE_GAIN:.0%} above the "
            f"champion's {champion_pr_auc:.3f}"
        )
    if challenger_pr_auc <= route_pr_auc:
        failures.append(
            f"PR-AUC {challenger_pr_auc:.3f} not above the route rule {route_pr_auc:.3f}"
        )
    if challenger_mae > champion_mae:
        failures.append(f"MAE {challenger_mae:.2f} worse than the champion's {champion_mae:.2f}")
    return GateResult(
        passed=not failures,
        reasons=failures,
        champion_pr_auc=champion_pr_auc,
        challenger_pr_auc=challenger_pr_auc,
        route_rule_pr_auc=route_pr_auc,
        champion_mae=champion_mae,
        challenger_mae=challenger_mae,
    )


def region_slices(
    regions: pd.Series, is_late: pd.Series, scores: np.ndarray, threshold: float,
    labelled: pd.Series,
) -> pd.DataFrame:  # fmt: skip
    """Late rate, flagged share, recall and PR-AUC per customer region (labelled orders)."""
    frame = pd.DataFrame(
        {
            "region": regions.to_numpy(),
            "is_late": is_late.to_numpy(dtype=int),
            "score": scores,
            "flagged": scores >= threshold,
        }
    )[labelled.to_numpy(dtype=bool)]
    records = []
    for region, group in frame.groupby("region", sort=True):
        positives = int(group["is_late"].sum())
        enough = positives >= SLICE_MIN_POSITIVES
        records.append(
            {
                "region": region,
                "orders": len(group),
                "late_rate": float(group["is_late"].mean()),
                "flagged_rate": float(group["flagged"].mean()),
                "recall": float(group.loc[group["is_late"] == 1, "flagged"].mean())
                if enough
                else float("nan"),
                "pr_auc": float(average_precision_score(group["is_late"], group["score"]))
                if enough
                else float("nan"),
            }
        )
    return pd.DataFrame(records)
