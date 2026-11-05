from datetime import date

import pandas as pd

from olist_platform.models.data import prepare
from olist_platform.models.report import write_report
from olist_platform.models.train import (
    CHAMPION_ALIAS,
    CLASSIFIER_NAME,
    REGRESSOR_NAME,
    run_training,
)
from tests.model_data import synthetic_deliveries


def test_prepare_keeps_the_window_and_attaches_history():
    data = prepare(synthetic_deliveries())
    assert data.rows["purchased_at"].min() >= pd.Timestamp("2017-01-01")
    assert data.rows["purchased_at"].max() < pd.Timestamp("2018-09-01")
    # Pre-window deliveries still feed the history of the first in-window orders.
    assert len(data.deliveries) > len(data.rows)
    assert data.rows["seller_prior_deliveries"].iloc[0] > 0


def test_training_registers_both_champions_and_writes_the_report(tmp_path):
    from mlflow import MlflowClient

    tracking_uri = f"sqlite:///{(tmp_path / 'mlflow.db').as_posix()}"
    outcome = run_training(prepare(synthetic_deliveries()), tracking_uri)

    client = MlflowClient(tracking_uri=tracking_uri)
    for name in (CLASSIFIER_NAME, REGRESSOR_NAME):
        version = client.get_model_version_by_alias(name, CHAMPION_ALIAS)
        assert str(version.version) == "1"
    classifier = client.get_model_version_by_alias(CLASSIFIER_NAME, CHAMPION_ALIAS)
    assert float(classifier.tags["threshold"]) > 0

    names = {r.name for r in outcome.classification.results}
    assert {"majority_class", "route_slack_rule", "logistic_regression", "lightgbm"} <= names
    assert {r.name for r in outcome.regression.results} >= {"olist_estimate", "ridge_regression"}
    assert len(outcome.explanation.examples) == 3

    report = write_report(outcome, tmp_path / "docs" / "modelagem.md", date(2026, 1, 1))
    text = report.read_text(encoding="utf-8")
    assert "(campeão)" in text
    assert "## Calibração do classificador campeão (teste)" in text
