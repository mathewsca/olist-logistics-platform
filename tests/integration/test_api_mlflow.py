"""The API's live path: champions pulled from the compose MLflow registry."""

import os

import pytest

from olist_platform.api.bundle import (
    CHAMPION_ALIAS,
    CLASSIFIER_NAME,
    export_geography,
    mlflow_is_reachable,
    resolve_bundle,
)
from olist_platform.api.schemas import ORDER_EXAMPLE, OrderRequest
from olist_platform.api.service import predict
from olist_platform.ingestion.settings import WarehouseSettings, load_dotenv_if_present

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def tracking_uri():
    load_dotenv_if_present()
    uri = os.environ.get("MLFLOW_TRACKING_URI", "http://localhost:5000")
    if not mlflow_is_reachable(uri):
        pytest.fail(f"MLflow not reachable at {uri} (did you run `make up` and `make train`?)")
    return uri


def test_serves_the_registered_champion(tracking_uri, tmp_path):
    from mlflow import MlflowClient

    export_geography(WarehouseSettings.from_env().conninfo(), tmp_path)
    bundle = resolve_bundle(tmp_path, tracking_uri)
    champion = MlflowClient(tracking_uri).get_model_version_by_alias(
        CLASSIFIER_NAME, CHAMPION_ALIAS
    )
    assert bundle.metadata["served_from"] == "mlflow"
    assert bundle.metadata["classifier"]["version"] == str(champion.version)
    assert bundle.threshold == pytest.approx(float(champion.tags["threshold"]))
    prediction = predict([OrderRequest.model_validate(ORDER_EXAMPLE)], bundle)[0]
    assert prediction.warnings == []
