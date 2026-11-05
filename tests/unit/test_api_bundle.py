"""Bundle layout on disk, the MLflow fallback and the names shared with training."""

import json

import numpy as np
import pytest

from olist_platform.api import bundle as api_bundle
from olist_platform.api.schemas import ORDER_EXAMPLE, OrderRequest
from olist_platform.api.service import predict
from olist_platform.models import train
from tests.api_data import fitted_bundle


@pytest.fixture(scope="module")
def bundle_dir(tmp_path_factory):
    import mlflow.sklearn

    source = fitted_bundle()
    directory = tmp_path_factory.mktemp("bundle")
    for role, pipeline in (("classifier", source.classifier), ("regressor", source.regressor)):
        mlflow.sklearn.save_model(
            pipeline,
            str(directory / role),
            skops_trusted_types=train.trusted_types(pipeline),
            pip_requirements=[],
        )
    source.seller_history.to_parquet(directory / api_bundle.SELLER_HISTORY_FILE)
    source.geography.reset_index().to_parquet(directory / api_bundle.GEOGRAPHY_FILE, index=False)
    (directory / api_bundle.METADATA_FILE).write_text(json.dumps(source.metadata))
    return directory, source


def test_saved_bundle_predicts_like_the_in_memory_one(bundle_dir):
    directory, source = bundle_dir
    loaded = api_bundle.load_bundle(directory)
    orders = [OrderRequest.model_validate(ORDER_EXAMPLE)]
    expected, actual = predict(orders, source)[0], predict(orders, loaded)[0]
    assert np.isclose(actual.late_risk_score, expected.late_risk_score)
    assert actual.predicted_delivery_days == expected.predicted_delivery_days
    assert loaded.threshold == source.threshold
    assert list(loaded.geography.index) == list(source.geography.index)


def test_unreachable_mlflow_falls_back_to_the_export(bundle_dir):
    directory, _ = bundle_dir
    # Port 9 (discard) is closed on any test machine, so the probe fails fast.
    loaded = api_bundle.resolve_bundle(directory, "http://127.0.0.1:9")
    assert loaded.metadata["served_from"] == "export"


@pytest.mark.parametrize("uri", ["mlruns", "file:///tmp/mlruns", "databricks"])
def test_non_server_tracking_uris_fall_back_to_the_export(bundle_dir, uri):
    directory, _ = bundle_dir
    assert api_bundle.resolve_bundle(directory, uri).metadata["served_from"] == "export"


def test_failed_export_keeps_the_previous_bundle(tmp_path, monkeypatch):
    previous = tmp_path / "models_export"
    previous.mkdir()
    (previous / "metadata.json").write_text("{}")

    def broken_download(tracking_uri, directory):
        directory.mkdir(parents=True)
        (directory / "classifier").mkdir()
        raise ConnectionError("registry went away")

    monkeypatch.setattr(api_bundle, "download_champions", broken_download)
    with pytest.raises(ConnectionError):
        api_bundle.export_bundle("http://mlflow:5000", "postgresql://", previous)
    assert (previous / "metadata.json").read_text() == "{}"
    assert not (previous / "classifier").exists()


def test_registry_names_match_training():
    assert api_bundle.CLASSIFIER_NAME == train.CLASSIFIER_NAME
    assert api_bundle.REGRESSOR_NAME == train.REGRESSOR_NAME
    assert api_bundle.CHAMPION_ALIAS == train.CHAMPION_ALIAS
