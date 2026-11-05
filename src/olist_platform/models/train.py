"""Train, compare and register the late-delivery classifier and the delivery-time regressor."""

import logging
import math
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from olist_platform.features import build_features, history_snapshot
from olist_platform.models.baselines import (
    MajorityClass,
    OlistEstimate,
    RouteMedian,
    RouteSlack,
    TrainMedian,
)
from olist_platform.models.data import TrainingData
from olist_platform.models.estimators import (
    Candidate,
    classification_candidates,
    regression_candidates,
)
from olist_platform.models.evaluation import (
    best_f1_threshold,
    calibration_table,
    classification_metrics,
    regression_metrics,
)
from olist_platform.models.explain import Explanation, explain
from olist_platform.models.split import Split, temporal_split

logger = logging.getLogger(__name__)

EXPERIMENT_NAME = "olist-delivery"
CLASSIFIER_NAME = "olist-late-delivery"
REGRESSOR_NAME = "olist-delivery-days"
CHAMPION_ALIAS = "champion"
MODEL_RUNTIME_PACKAGES = ("scikit-learn", "lightgbm", "skops", "numpy", "pandas", "scipy")
# MLflow saves scikit-learn models with skops (no arbitrary pickle code on load), which only
# accepts listed types; these libraries are the ones the pipelines are built from.
TRUSTED_MODULE_PREFIXES = (
    "numpy.",
    "sklearn.",
    "lightgbm.",
    "scipy.",
    "builtins.",
    "collections.OrderedDict",
)


@dataclass
class MethodResult:
    """One baseline or model evaluated on validation and test."""

    name: str
    kind: str
    validation: dict[str, float]
    test: dict[str, float]
    threshold: float | None = None


@dataclass
class TaskOutcome:
    """Every method of a task, the champion and what was registered."""

    results: list[MethodResult]
    champion: str
    registered_version: str | None = None
    extras: dict = field(default_factory=dict)


@dataclass
class TrainingOutcome:
    """What the report needs."""

    split: Split
    classification: TaskOutcome
    regression: TaskOutcome
    explanation: Explanation
    calibration: pd.DataFrame


@dataclass(frozen=True)
class Matrices:
    """Features and both targets of each split part."""

    features: dict[str, pd.DataFrame]
    is_late: dict[str, pd.Series]
    delivery_days: dict[str, pd.Series]


PARTS = ("train", "validation", "test")


def build_matrices(split: Split) -> Matrices:
    """Features through the shared module, so training sees exactly what the API will compute."""
    frames = {part: getattr(split, part) for part in PARTS}
    return Matrices(
        features={part: build_features(frame) for part, frame in frames.items()},
        is_late={part: frame["is_late"].astype(int) for part, frame in frames.items()},
        delivery_days={
            part: frame["delivery_days"].astype(float) for part, frame in frames.items()
        },
    )


def _log_metrics(mlflow, result: MethodResult) -> None:
    for part in ("validation", "test"):
        for metric, value in getattr(result, part).items():
            if not math.isnan(value):
                mlflow.log_metric(f"{part}_{metric}", value)
    if result.threshold is not None:
        mlflow.log_metric("threshold", result.threshold)


def _classification_baselines(m: Matrices) -> list[MethodResult]:
    results = []
    majority = MajorityClass().fit(m.features["train"], m.is_late["train"])
    # Never flags an order, as trusting the promise would; its threshold sits above every score.
    results.append(
        MethodResult(
            "majority_class",
            "baseline",
            *(
                classification_metrics(
                    m.is_late[part], majority.score(m.features[part]), np.inf, is_probability=True
                )
                for part in ("validation", "test")
            ),
            threshold=None,
        )
    )
    slack = RouteSlack().fit(m.features["train"], m.delivery_days["train"])
    threshold = best_f1_threshold(m.is_late["validation"], slack.score(m.features["validation"]))
    results.append(
        MethodResult(
            "route_slack_rule",
            "baseline",
            *(
                classification_metrics(
                    m.is_late[part], slack.score(m.features[part]), threshold, is_probability=False
                )
                for part in ("validation", "test")
            ),
            threshold=threshold,
        )
    )
    return results


def _fit(candidate: Candidate, features: pd.DataFrame, target: pd.Series) -> None:
    candidate.pipeline.fit(features, target, **candidate.fit_params)


def trusted_types(pipeline) -> list[str]:
    """Types skops must accept to load ``pipeline``; anything outside the known libraries fails."""
    import skops.io

    untrusted = skops.io.get_untrusted_types(data=skops.io.dumps(pipeline))
    unexpected = [name for name in untrusted if not name.startswith(TRUSTED_MODULE_PREFIXES)]
    if unexpected:
        raise RuntimeError(f"Pipeline references unexpected types: {', '.join(unexpected)}")
    return untrusted


def _log_model(mlflow, candidate: Candidate, sample: pd.DataFrame, output: np.ndarray) -> str:
    from mlflow.models import infer_signature

    info = mlflow.sklearn.log_model(
        sk_model=candidate.pipeline,
        name="model",
        signature=infer_signature(sample, output),
        skops_trusted_types=trusted_types(candidate.pipeline),
        pip_requirements=model_requirements(),
    )
    return info.model_uri


def model_requirements() -> list[str]:
    """Pinned runtime requirements of the logged pipelines.

    Listed explicitly because MLflow's inference loads every model in a subprocess (slow) and
    still misses the features package the API installs on its own.
    """
    from importlib.metadata import version

    return [f"{name}=={version(name)}" for name in MODEL_RUNTIME_PACKAGES]


def _register(client, model_uri: str, name: str, tags: dict[str, str]) -> str:
    import mlflow

    version = mlflow.register_model(model_uri, name)
    for key, value in tags.items():
        client.set_model_version_tag(name, version.version, key, value)
    client.set_registered_model_alias(name, CHAMPION_ALIAS, version.version)
    return str(version.version)


def train_classifier(mlflow, client, m: Matrices, snapshot_dir: Path) -> TaskOutcome:
    """Baselines, candidates, threshold on validation, champion by validation PR-AUC."""
    results = _classification_baselines(m)
    positive_rate = float(m.is_late["train"].mean())
    fitted: dict[str, tuple[Candidate, str, float, np.ndarray]] = {}
    for candidate in classification_candidates(positive_rate):
        with mlflow.start_run(run_name=f"classifier/{candidate.name}", nested=True):
            _fit(candidate, m.features["train"], m.is_late["train"])
            scores = {
                part: candidate.pipeline.predict_proba(m.features[part])[:, 1]
                for part in ("validation", "test")
            }
            threshold = best_f1_threshold(m.is_late["validation"], scores["validation"])
            result = MethodResult(
                candidate.name,
                "model",
                *(
                    classification_metrics(
                        m.is_late[part], scores[part], threshold, is_probability=True
                    )
                    for part in ("validation", "test")
                ),
                threshold=threshold,
            )
            mlflow.set_tags({"task": "classification", "target": "is_late"})
            mlflow.log_params(candidate.pipeline[-1].get_params())
            _log_metrics(mlflow, result)
            mlflow.log_artifacts(str(snapshot_dir), artifact_path="seller_history")
            uri = _log_model(
                mlflow, candidate, m.features["validation"].head(200), scores["validation"][:200]
            )
            results.append(result)
            fitted[candidate.name] = (candidate, uri, threshold, scores["test"])
            logger.info(
                "classifier %s: validation PR-AUC %.4f", candidate.name, result.validation["pr_auc"]
            )

    models = [r for r in results if r.kind == "model"]
    champion = max(models, key=lambda r: r.validation["pr_auc"])
    candidate, uri, threshold, champion_test_scores = fitted[champion.name]
    # Exact value: the API compares scores against it, and rounding would move borderline orders.
    version = _register(
        client, uri, CLASSIFIER_NAME, {"threshold": repr(threshold), "algorithm": champion.name}
    )
    # SHAP needs a tree model; if a linear model wins, the best tree is explained instead.
    trees = [r for r in models if fitted[r.name][0].is_tree]
    explained = champion if candidate.is_tree else max(trees, key=lambda r: r.validation["pr_auc"])
    return TaskOutcome(
        results,
        champion.name,
        version,
        extras={
            "explained": explained.name,
            "pipeline": fitted[explained.name][0].pipeline,
            "explained_test_scores": fitted[explained.name][3],
            "champion_test_scores": champion_test_scores,
            "threshold": threshold,
        },
    )


def _regression_baselines(m: Matrices) -> list[MethodResult]:
    results = []
    for name, baseline in (
        ("olist_estimate", OlistEstimate()),
        ("train_median", TrainMedian()),
        ("route_median", RouteMedian()),
    ):
        baseline.fit(m.features["train"], m.delivery_days["train"])
        results.append(
            MethodResult(
                name,
                "baseline",
                *(
                    regression_metrics(m.delivery_days[part], baseline.predict(m.features[part]))
                    for part in ("validation", "test")
                ),
            )
        )
    return results


def train_regressor(mlflow, client, m: Matrices, snapshot_dir: Path) -> TaskOutcome:
    """Baselines and candidates for delivery days; champion by validation MAE."""
    results = _regression_baselines(m)
    uris = {}
    for candidate in regression_candidates():
        with mlflow.start_run(run_name=f"regressor/{candidate.name}", nested=True):
            _fit(candidate, m.features["train"], m.delivery_days["train"])
            predictions = {
                part: candidate.pipeline.predict(m.features[part])
                for part in ("validation", "test")
            }
            result = MethodResult(
                candidate.name,
                "model",
                *(
                    regression_metrics(m.delivery_days[part], predictions[part])
                    for part in ("validation", "test")
                ),
            )
            mlflow.set_tags({"task": "regression", "target": "delivery_days"})
            mlflow.log_params(candidate.pipeline[-1].get_params())
            _log_metrics(mlflow, result)
            mlflow.log_artifacts(str(snapshot_dir), artifact_path="seller_history")
            uris[candidate.name] = _log_model(
                mlflow,
                candidate,
                m.features["validation"].head(200),
                predictions["validation"][:200],
            )
            results.append(result)
            logger.info(
                "regressor %s: validation MAE %.3f", candidate.name, result.validation["mae"]
            )

    champion = min((r for r in results if r.kind == "model"), key=lambda r: r.validation["mae"])
    version = _register(client, uris[champion.name], REGRESSOR_NAME, {"algorithm": champion.name})
    return TaskOutcome(results, champion.name, version)


def write_snapshot(data: TrainingData, directory: Path) -> Path:
    """Seller history frozen at the last known delivery, the lookup table the API will serve."""
    as_of = data.deliveries["delivered_at"].max() + pd.Timedelta(seconds=1)
    snapshot = history_snapshot(data.deliveries, as_of)
    path = directory / "seller_history.parquet"
    snapshot.to_parquet(path)
    (directory / "as_of.txt").write_text(f"{as_of.isoformat()}\n", encoding="utf-8", newline="\n")
    return path


def run_training(data: TrainingData, tracking_uri: str) -> TrainingOutcome:
    """Full training run tracked in MLflow; registers both champions with the ``champion`` alias."""
    import mlflow
    from mlflow import MlflowClient

    mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_experiment(EXPERIMENT_NAME)
    client = MlflowClient()

    split = temporal_split(data.rows)
    summary = split.summary()
    logger.info("split:\n%s", summary.to_string(index=False))
    matrices = build_matrices(split)

    with tempfile.TemporaryDirectory() as tmp, mlflow.start_run(run_name="training"):
        snapshot_dir = Path(tmp)
        write_snapshot(data, snapshot_dir)
        for row in summary.itertuples():
            mlflow.log_param(f"{row.part}_rows", row.rows)
            mlflow.log_param(f"{row.part}_period", f"{row.first_purchase}..{row.last_purchase}")

        classification = train_classifier(mlflow, client, matrices, snapshot_dir)
        regression = train_regressor(mlflow, client, matrices, snapshot_dir)
        for outcome in (classification, regression):
            for result in outcome.results:
                if result.kind == "baseline":
                    for metric, value in result.test.items():
                        if not math.isnan(value):
                            mlflow.log_metric(f"baseline_{result.name}_test_{metric}", value)

    calibration = calibration_table(
        matrices.is_late["test"], classification.extras["champion_test_scores"]
    )
    explanation = explain(
        classification.extras["pipeline"],
        matrices.features["test"],
        matrices.is_late["test"],
        classification.extras["explained_test_scores"],
    )
    return TrainingOutcome(split, classification, regression, explanation, calibration)
