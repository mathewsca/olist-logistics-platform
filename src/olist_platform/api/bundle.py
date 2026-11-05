"""What the API serves: both champions, the seller-history snapshot and the zip-prefix lookup.

A bundle is a directory with one fixed layout, filled either from the MLflow registry or by
``make export-model`` (the fallback baked into the deploy image).
"""

import json
import logging
import os
import shutil
import tempfile
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)

# Same values as olist_platform.models.train (a test checks it); not imported, so the API image
# needs no training dependencies.
CLASSIFIER_NAME = "olist-late-delivery"
REGRESSOR_NAME = "olist-delivery-days"
CHAMPION_ALIAS = "champion"
SELLER_HISTORY_ARTIFACT = "seller_history"

METADATA_FILE = "metadata.json"
SELLER_HISTORY_FILE = "seller_history.parquet"
GEOGRAPHY_FILE = "geography.parquet"
MODEL_DIRS = {"classifier": CLASSIFIER_NAME, "regressor": REGRESSOR_NAME}

GEOGRAPHY_SQL = "select zip_code_prefix, latitude, longitude from marts.dim_geography"


@dataclass(frozen=True)
class ModelBundle:
    """Loaded models and lookup tables, plus where they came from."""

    classifier: Any
    regressor: Any
    threshold: float
    seller_history: pd.DataFrame
    geography: pd.DataFrame
    metadata: dict


def load_bundle(directory: Path, geography_path: Path | None = None) -> ModelBundle:
    """Load a bundle directory; ``geography_path`` overrides the table inside it."""
    import mlflow.sklearn

    directory = Path(directory)
    metadata = json.loads((directory / METADATA_FILE).read_text(encoding="utf-8"))
    geography = pd.read_parquet(geography_path or directory / GEOGRAPHY_FILE)
    if "zip_code_prefix" in geography.columns:
        geography = geography.set_index("zip_code_prefix")
    return ModelBundle(
        classifier=mlflow.sklearn.load_model(str(directory / "classifier")),
        regressor=mlflow.sklearn.load_model(str(directory / "regressor")),
        threshold=float(metadata["classifier"]["threshold"]),
        seller_history=pd.read_parquet(directory / SELLER_HISTORY_FILE),
        geography=geography,
        metadata=metadata,
    )


def mlflow_is_reachable(tracking_uri: str, timeout: float = 3.0) -> bool:
    """Quick health probe: the MLflow client itself retries for minutes before failing.

    Only a tracking server counts; a local store (``mlruns``, ``file://``) is not served here.
    """
    if not tracking_uri.startswith(("http://", "https://")):
        return False
    try:
        with urllib.request.urlopen(f"{tracking_uri.rstrip('/')}/health", timeout=timeout):
            return True
    except (OSError, ValueError):
        return False


def download_champions(tracking_uri: str, directory: Path) -> dict:
    """Copy both ``champion`` models and the classifier run's seller snapshot into ``directory``.

    ``directory`` must be new or empty; ``export_bundle`` builds one and swaps it in.
    """
    import mlflow
    from mlflow import MlflowClient

    # Progress bars flood container logs; the export logs a summary instead.
    os.environ.setdefault("MLFLOW_ENABLE_ARTIFACTS_PROGRESS_BAR", "false")
    mlflow.set_tracking_uri(tracking_uri)
    client = MlflowClient()
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    metadata: dict[str, Any] = {"source": tracking_uri}
    for role, name in MODEL_DIRS.items():
        version = client.get_model_version_by_alias(name, CHAMPION_ALIAS)
        # By number, not alias: a `make train` moving the alias meanwhile must not mix versions.
        mlflow.artifacts.download_artifacts(
            artifact_uri=f"models:/{name}/{version.version}", dst_path=str(directory / role)
        )
        metadata[role] = {
            "name": name,
            "version": str(version.version),
            "algorithm": version.tags.get("algorithm"),
            "run_id": version.run_id,
        }
        if role == "classifier":
            metadata[role]["threshold"] = float(version.tags["threshold"])

    with tempfile.TemporaryDirectory() as tmp:
        snapshot_dir = Path(
            mlflow.artifacts.download_artifacts(
                run_id=metadata["classifier"]["run_id"],
                artifact_path=SELLER_HISTORY_ARTIFACT,
                dst_path=tmp,
            )
        )
        shutil.copy(snapshot_dir / SELLER_HISTORY_FILE, directory / SELLER_HISTORY_FILE)
        metadata["seller_history_as_of"] = (snapshot_dir / "as_of.txt").read_text().strip()

    metadata["exported_at"] = datetime.now(UTC).isoformat(timespec="seconds")
    (directory / METADATA_FILE).write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    return metadata


def export_geography(conninfo: str, directory: Path) -> Path:
    """Zip prefix -> median coordinates from ``dim_geography``, the same table training joins."""
    import psycopg

    with psycopg.connect(conninfo) as conn:
        rows = conn.execute(GEOGRAPHY_SQL).fetchall()
    geography = pd.DataFrame(rows, columns=["zip_code_prefix", "latitude", "longitude"])
    path = Path(directory) / GEOGRAPHY_FILE
    geography.to_parquet(path, index=False)
    return path


def export_bundle(tracking_uri: str, conninfo: str, directory: Path) -> dict:
    """Build a complete bundle next to ``directory`` and only then replace it.

    A failure halfway (MLflow, Postgres) leaves the previous bundle intact instead of a mix of
    old and new files that the next image build would bake in.
    """
    directory = Path(directory)
    staging = directory.with_name(f"{directory.name}.partial")
    if staging.exists():
        shutil.rmtree(staging)
    metadata = download_champions(tracking_uri, staging)
    export_geography(conninfo, staging)
    if directory.exists():
        shutil.rmtree(directory)
    staging.rename(directory)
    return metadata


def resolve_bundle(bundle_dir: Path, tracking_uri: str | None) -> ModelBundle:
    """The registry's current champions when MLflow answers, otherwise the exported bundle."""
    bundle_dir = Path(bundle_dir)
    if tracking_uri and mlflow_is_reachable(tracking_uri):
        try:
            # Everything is read into memory, so the downloaded copy can go right away.
            with tempfile.TemporaryDirectory(prefix="olist-api-") as live_dir:
                download_champions(tracking_uri, Path(live_dir))
                bundle = load_bundle(Path(live_dir), geography_path=bundle_dir / GEOGRAPHY_FILE)
            bundle.metadata["served_from"] = "mlflow"
            logger.info("Serving champions from MLflow at %s", tracking_uri)
            return bundle
        except Exception:
            logger.exception("Could not load champions from MLflow; using %s", bundle_dir)
    elif tracking_uri:
        logger.warning("MLflow at %s not reachable; using %s", tracking_uri, bundle_dir)
    bundle = load_bundle(bundle_dir)
    bundle.metadata["served_from"] = "export"
    return bundle
