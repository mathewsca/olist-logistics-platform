"""The simulation's own registry entries, apart from the API's champions."""

import tempfile
from pathlib import Path

import pandas as pd

from olist_platform.models.train import CHAMPION_ALIAS, model_requirements, trusted_types
from olist_platform.monitoring.retrain import ModelPair
from olist_platform.monitoring.windows import FitWindow

EXPERIMENT_NAME = "olist-monitoring-simulation"
# Separate names: replaying 2018 must not move the alias the API serves from.
CLASSIFIER_NAME = "olist-late-delivery-sim"
REGRESSOR_NAME = "olist-delivery-days-sim"
SERVING_ARTIFACTS = "serving"
# Enough rows for stable drift statistics; the full training matrix would bloat every run.
REFERENCE_SAMPLE_SIZE = 20_000
VALIDATION_TAGS = ("pr_auc", "late_rate", "lift", "recall", "mae")


def _log_model(mlflow, pipeline, name: str) -> str:
    info = mlflow.sklearn.log_model(
        sk_model=pipeline,
        name=name,
        skops_trusted_types=trusted_types(pipeline),
        pip_requirements=model_requirements(),
    )
    return info.model_uri


def log_pair(pair: ModelPair, run_name: str, role: str) -> dict[str, str]:
    """Log and register both models of ``pair``; returns the new version of each name."""
    import mlflow
    from mlflow import MlflowClient

    mlflow.set_experiment(EXPERIMENT_NAME)
    client = MlflowClient()
    reference = pair.reference.sample(
        min(REFERENCE_SAMPLE_SIZE, len(pair.reference)), random_state=0
    )
    tags = {
        "role": role,
        "threshold": repr(pair.threshold),
        "data_end": pair.window.data_end.date().isoformat(),
        "label_cutoff": pair.window.label_cutoff.date().isoformat(),
        "classifier_algorithm": pair.classifier_name,
        "regressor_algorithm": pair.regressor_name,
        **{f"validation_{key}": repr(pair.validation[key]) for key in VALIDATION_TAGS},
    }
    versions = {}
    with mlflow.start_run(run_name=run_name), tempfile.TemporaryDirectory() as tmp:
        mlflow.set_tags(tags)
        mlflow.log_metrics({f"validation_{k}": v for k, v in pair.validation.items()})
        pair.seller_history.to_parquet(Path(tmp) / "seller_history.parquet")
        reference.to_parquet(Path(tmp) / "reference.parquet")
        mlflow.log_artifacts(tmp, artifact_path=SERVING_ARTIFACTS)
        for name, pipeline, model_name in (
            (CLASSIFIER_NAME, pair.classifier, "classifier"),
            (REGRESSOR_NAME, pair.regressor, "regressor"),
        ):
            # Tags go in with the version, so a failure never leaves one half-tagged.
            version = mlflow.register_model(
                _log_model(mlflow, pipeline, model_name), name, tags=tags
            )
            versions[name] = str(version.version)
        # The classifier version identifies the pair; it points to its regressor.
        client.set_model_version_tag(
            CLASSIFIER_NAME,
            versions[CLASSIFIER_NAME],
            "regressor_version",
            versions[REGRESSOR_NAME],
        )
    return versions


def log_evaluation(month: pd.Period, metrics: dict[str, float], report_path: Path) -> str:
    """Log one month's evaluation with its Evidently report; returns the report's MLflow URI."""
    import mlflow

    mlflow.set_experiment(EXPERIMENT_NAME)
    with mlflow.start_run(run_name=f"evaluate-{month}") as run:
        mlflow.set_tags({"role": "evaluation", "month": str(month)})
        mlflow.log_metrics({k: v for k, v in metrics.items() if v is not None and v == v})
        mlflow.log_artifact(str(report_path))
    return f"runs:/{run.info.run_id}/{Path(report_path).name}"


def promote(
    versions: dict[str, str], serving_from: pd.Timestamp, validated_by: str | None = None
) -> None:
    """Move ``champion`` to both versions; ``serving_from`` is the simulated date it goes live.

    ``validated_by`` is the gate fit (classifier version) whose recipe this refit repeats.
    """
    from mlflow import MlflowClient

    client = MlflowClient()
    for name, version in versions.items():
        client.set_model_version_tag(name, version, "gate", "promoted")
        client.set_model_version_tag(name, version, "serving_from", serving_from.date().isoformat())
        if validated_by is not None:
            client.set_model_version_tag(name, version, "validated_by", validated_by)
        client.set_registered_model_alias(name, CHAMPION_ALIAS, version)


def mark_gate_passed(versions: dict[str, str]) -> None:
    """Keep the gate fit for the record: it passed, but the refit on newer data is what serves."""
    from mlflow import MlflowClient

    client = MlflowClient()
    for name, version in versions.items():
        client.set_model_version_tag(name, version, "gate", "passed")


def reject(versions: dict[str, str], reasons: list[str]) -> None:
    """Keep a failed challenger for the record, without the alias."""
    from mlflow import MlflowClient

    client = MlflowClient()
    for name, version in versions.items():
        client.set_model_version_tag(name, version, "gate", "rejected")
        client.set_model_version_tag(name, version, "gate_reasons", "; ".join(reasons)[:5000])


def _promoted_versions() -> list:
    from mlflow import MlflowClient

    found = MlflowClient().search_model_versions(f"name='{CLASSIFIER_NAME}'")
    return [v for v in found if v.tags.get("gate") == "promoted"]


def serving_version(as_of: pd.Timestamp) -> str | None:
    """Classifier version that was live at ``as_of`` (latest promotion not after it).

    A month is scored by the pair serving when it began, not by today's champion: a pair
    promoted later carries a seller snapshot that already contains that month's deliveries.
    """
    # A pair whose labels reach past ``as_of`` would score with information from the future.
    live = [
        v
        for v in _promoted_versions()
        if pd.Timestamp(v.tags["serving_from"]) <= as_of
        and pd.Timestamp(v.tags["label_cutoff"]) <= as_of
    ]
    if not live:
        return None
    return str(max(live, key=lambda v: (v.tags["serving_from"], int(v.version))).version)


def load_pair(classifier_version: str) -> tuple[ModelPair, dict[str, str]]:
    """A registered pair with its snapshot, reference sample and validation metrics."""
    import mlflow
    from mlflow import MlflowClient

    client = MlflowClient()
    classifier = client.get_model_version(CLASSIFIER_NAME, classifier_version)
    tags = classifier.tags
    versions = {
        CLASSIFIER_NAME: classifier_version,
        REGRESSOR_NAME: tags["regressor_version"],
    }
    with tempfile.TemporaryDirectory() as tmp:
        serving = Path(
            mlflow.artifacts.download_artifacts(
                run_id=classifier.run_id, artifact_path=SERVING_ARTIFACTS, dst_path=tmp
            )
        )
        seller_history = pd.read_parquet(serving / "seller_history.parquet")
        reference = pd.read_parquet(serving / "reference.parquet")
    pair = ModelPair(
        classifier=mlflow.sklearn.load_model(f"models:/{CLASSIFIER_NAME}/{classifier_version}"),
        regressor=mlflow.sklearn.load_model(f"models:/{REGRESSOR_NAME}/{versions[REGRESSOR_NAME]}"),
        threshold=float(tags["threshold"]),
        seller_history=seller_history,
        window=FitWindow(pd.Timestamp(tags["data_end"]), pd.Timestamp(tags["label_cutoff"])),
        classifier_name=tags["classifier_algorithm"],
        regressor_name=tags["regressor_algorithm"],
        validation={key: float(tags[f"validation_{key}"]) for key in VALIDATION_TAGS},
        reference=reference,
    )
    return pair, versions


def reset() -> None:
    """Forget every simulation model so a replay starts from the bootstrap."""
    from mlflow import MlflowClient
    from mlflow.exceptions import MlflowException

    client = MlflowClient()
    for name in (CLASSIFIER_NAME, REGRESSOR_NAME):
        try:
            client.delete_registered_model(name)
        except MlflowException as error:
            # Only "never registered" is fine: a stale promoted version would leak into the replay.
            if error.error_code != "RESOURCE_DOES_NOT_EXIST":
                raise
