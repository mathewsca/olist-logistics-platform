"""Replay 2018-04..08 as production: score, monitor, retrain and gate, month by month.

Each public function is one Airflow task; state between them lives in MLflow and ``ml.*``.
"""

import logging
import tempfile
from pathlib import Path

import pandas as pd

from olist_platform.features import SELLER_HISTORY_COLUMNS, history_snapshot
from olist_platform.models.data import TrainingData
from olist_platform.monitoring import registry, store
from olist_platform.monitoring.drift import drift_summary
from olist_platform.monitoring.performance import (
    month_performance,
    quality_gate,
    region_slices,
    retrain_reasons,
)
from olist_platform.monitoring.retrain import ModelPair, fit_pair, score, serving_features
from olist_platform.monitoring.windows import (
    MONITORED_MONTHS,
    SIMULATION_START,
    bootstrap_window,
    challenger_window,
    evaluated_at,
    gate_window,
)

logger = logging.getLogger(__name__)

# Still model inputs, but not data drift: one purchase month always differs from a year-long
# reference (the calendar), and the served seller history only measures how old the frozen
# snapshot is (it stops growing while the pair is live).
DRIFT_EXCLUDED_FEATURES = ("purchase_month", *SELLER_HISTORY_COLUMNS)


def month_rows(data: TrainingData, month: pd.Period) -> pd.DataFrame:
    """Orders bought in ``month`` (the population of ``fct_deliveries``)."""
    purchased = data.rows["purchased_at"]
    return data.rows[(purchased >= month.start_time) & (purchased <= month.end_time)]


def bootstrap(data: TrainingData) -> dict[str, str]:
    """Start a replay: forget earlier runs and put the first pair in production."""
    registry.reset()
    pair = fit_pair(data, bootstrap_window())
    versions = registry.log_pair(pair, run_name="bootstrap", role="bootstrap")
    registry.promote(versions, serving_from=SIMULATION_START)
    logger.info("Bootstrap pair %s (%s, %s)", versions, pair.classifier_name, pair.regressor_name)
    return versions


def _serving_pair(month: pd.Period) -> tuple[ModelPair, dict[str, str]]:
    version = registry.serving_version(month.start_time)
    if version is None:
        raise RuntimeError("No pair in production yet: run the bootstrap first")
    return registry.load_pair(version)


def evaluate_month(data: TrainingData, month: pd.Period, conn) -> dict:
    """Score the month as production did, measure drift and performance, decide on retraining."""
    pair, versions = _serving_pair(month)
    rows = month_rows(data, month)
    at = evaluated_at(month)
    features = serving_features(rows, pair)
    scores, days = score(pair, features)
    labelled = rows["delivered_to_customer_at"] < at
    performance = month_performance(
        rows["is_late"], rows["delivery_days"], scores, days, pair.threshold, labelled
    )

    with tempfile.TemporaryDirectory() as tmp:
        report_path = Path(tmp) / "drift_report.html"
        drift = drift_summary(
            pair.reference.drop(columns=list(DRIFT_EXCLUDED_FEATURES)),
            features.drop(columns=list(DRIFT_EXCLUDED_FEATURES)),
            report_path,
        )
        report_uri = registry.log_evaluation(
            month, {**vars(performance), "drift_share": drift.share}, report_path
        )
    reasons = retrain_reasons(drift.share, performance, pair.validation)
    record = {
        "month": month.start_time.date(),
        "evaluated_at": at.date(),
        "champion_version": versions[registry.CLASSIFIER_NAME],
        "champion_label_cutoff": pair.window.label_cutoff.date(),
        **vars(performance),
        "validation_lift": pair.validation["lift"],
        "validation_mae": pair.validation["mae"],
        "drift_share": drift.share,
        "drifted_features": len(drift.drifted),
        "drift_report": report_uri,
        "retrain_reasons": "; ".join(reasons) or None,
    }
    slices = region_slices(
        rows["destination_region"], rows["is_late"], scores, pair.threshold, labelled
    )
    store.save_month(conn, record, slices)
    logger.info("%s: lift %.2f, drift %.0f%%, retrain=%s", month, performance.lift,
                100 * drift.share, bool(reasons))  # fmt: skip
    return {"month": str(month), "retrain": bool(reasons), "reasons": reasons}


def _gate_scores(rows: pd.DataFrame, pair: ModelPair, seller_history: pd.DataFrame):
    features = serving_features(rows, ModelPair(**{**vars(pair), "seller_history": seller_history}))
    return features, score(pair, features)


def retrain_and_gate(data: TrainingData, month: pd.Period, conn) -> dict:
    """Validate the retraining recipe on ``month``, then refit and promote it only if it wins.

    The gate pits the pair that served ``month`` against the recipe refit with what was known when
    the month began, so neither side learned from labels that arrived during it. A recipe that
    passes is refit on everything known at the evaluation date, and that refit is promoted.
    """
    champion, _ = _serving_pair(month)
    candidate = fit_pair(data, gate_window(month))
    rows = month_rows(data, month)
    rows = rows[rows["delivered_to_customer_at"] < evaluated_at(month)]
    # Both sides see the seller history of the month's start, so the gate compares the models,
    # not how stale each snapshot is.
    month_start_history = history_snapshot(data.deliveries, month.start_time)
    _, champion_scores = _gate_scores(rows, champion, month_start_history)
    candidate_features, candidate_scores = _gate_scores(rows, candidate, month_start_history)
    result = quality_gate(
        rows["is_late"].to_numpy(),
        rows["delivery_days"].to_numpy(),
        champion=champion_scores,
        challenger=candidate_scores,
        route_rule_scores=candidate.route_rule.score(candidate_features),
    )
    gate_versions = registry.log_pair(candidate, run_name=f"gate-{month}", role="gate")
    if result.passed:
        registry.mark_gate_passed(gate_versions)
        challenger = fit_pair(data, challenger_window(month))
        versions = registry.log_pair(challenger, run_name=f"challenger-{month}", role="challenger")
        registry.promote(
            versions,
            serving_from=evaluated_at(month),
            validated_by=gate_versions[registry.CLASSIFIER_NAME],
        )
    else:
        versions = gate_versions
        registry.reject(versions, result.reasons)
    detail = (
        f"PR-AUC challenger {result.challenger_pr_auc:.3f} vs champion "
        f"{result.champion_pr_auc:.3f} (route rule {result.route_rule_pr_auc:.3f}); "
        f"MAE {result.challenger_mae:.2f} vs {result.champion_mae:.2f}"
    )
    if result.reasons:
        detail += ". " + "; ".join(result.reasons)
    store.save_gate(conn, month.start_time.date(), versions[registry.CLASSIFIER_NAME],
                    result.passed, detail)  # fmt: skip
    logger.info("%s gate: %s. %s", month, "promoted" if result.passed else "rejected", detail)
    return {"month": str(month), "promoted": result.passed, "detail": detail}


def simulate(data: TrainingData, conn) -> pd.DataFrame:
    """The whole replay from scratch: bootstrap, then every month in order."""
    store.reset(conn)
    bootstrap(data)
    for month in MONITORED_MONTHS:
        outcome = evaluate_month(data, month, conn)
        if outcome["retrain"]:
            retrain_and_gate(data, month, conn)
    return store.load_runs(conn)
