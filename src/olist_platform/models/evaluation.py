"""Metrics for both tasks and the decision threshold."""

import numpy as np
import pandas as pd
from sklearn.calibration import calibration_curve
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    f1_score,
    mean_absolute_error,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
    root_mean_squared_error,
)


def best_f1_threshold(target: np.ndarray, scores: np.ndarray) -> float:
    """Score cut-off with the highest F1 (chosen on validation, then frozen for test)."""
    precision, recall, thresholds = precision_recall_curve(target, scores)
    # The last precision/recall pair has no threshold (it is the 'predict nothing' point).
    f1 = 2 * precision[:-1] * recall[:-1] / np.clip(precision[:-1] + recall[:-1], 1e-12, None)
    return float(thresholds[int(np.argmax(f1))])


def classification_metrics(
    target: np.ndarray, scores: np.ndarray, threshold: float, is_probability: bool
) -> dict[str, float]:
    """Ranking metrics on the scores, decision metrics at the threshold, Brier if calibrated-ish."""
    target = np.asarray(target, dtype=int)
    predicted = (np.asarray(scores) >= threshold).astype(int)
    metrics = {
        "pr_auc": float(average_precision_score(target, scores)),
        "roc_auc": float(roc_auc_score(target, scores)),
        "f1": float(f1_score(target, predicted, zero_division=0)),
        "precision": float(precision_score(target, predicted, zero_division=0)),
        "recall": float(recall_score(target, predicted, zero_division=0)),
        "flagged_rate": float(predicted.mean()),
    }
    metrics["brier"] = float(brier_score_loss(target, scores)) if is_probability else float("nan")
    return metrics


def regression_metrics(target: np.ndarray, predicted: np.ndarray) -> dict[str, float]:
    """MAE, RMSE and mean bias (positive = forecasts longer than reality)."""
    target = np.asarray(target, dtype=float)
    predicted = np.asarray(predicted, dtype=float)
    return {
        "mae": float(mean_absolute_error(target, predicted)),
        "rmse": float(root_mean_squared_error(target, predicted)),
        "bias": float(np.mean(predicted - target)),
    }


def calibration_table(
    target: np.ndarray, probabilities: np.ndarray, bins: int = 10
) -> pd.DataFrame:
    """Observed late rate per decile of predicted probability."""
    observed, predicted = calibration_curve(target, probabilities, n_bins=bins, strategy="quantile")
    return pd.DataFrame({"mean_predicted": predicted, "observed_rate": observed})
