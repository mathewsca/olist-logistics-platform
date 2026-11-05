from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from olist_platform.models.data import prepare
from olist_platform.models.train import CHAMPION_ALIAS
from olist_platform.monitoring import registry, simulation
from olist_platform.monitoring.report import write_report
from olist_platform.monitoring.store import RUN_COLUMNS
from olist_platform.monitoring.windows import MONITORED_MONTHS, SIMULATION_START
from tests.model_data import synthetic_deliveries


class MemoryStore:
    """Stands in for ``ml.monitoring_*`` so the replay runs without Postgres."""

    def __init__(self):
        self.runs: dict = {}
        self.slices: dict = {}

    def reset(self, conn):
        self.runs.clear()
        self.slices.clear()

    def save_month(self, conn, record, slices):
        self.runs[record["month"]] = {column: record.get(column) for column in RUN_COLUMNS} | {
            "challenger_version": None,
            "gate_passed": None,
            "gate_detail": None,
        }
        self.slices[record["month"]] = slices.assign(month=record["month"])

    def save_gate(self, conn, month, challenger_version, passed, detail):
        self.runs[month].update(
            challenger_version=challenger_version, gate_passed=passed, gate_detail=detail
        )

    def load_runs(self, conn):
        return pd.DataFrame([self.runs[month] for month in sorted(self.runs)])

    def load_slices(self, conn):
        return pd.concat(self.slices.values(), ignore_index=True)


@pytest.fixture(scope="module")
def replay(tmp_path_factory):
    import mlflow

    tmp = tmp_path_factory.mktemp("replay")
    mlflow.set_tracking_uri(f"sqlite:///{(tmp / 'mlflow.db').as_posix()}")
    store = MemoryStore()
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(simulation, "store", store)
        # Every month retrains, so the challenger path and the gate run on each one.
        patch.setattr(simulation, "retrain_reasons", lambda *args: ["forced by the test"])
        runs = simulation.simulate(prepare(synthetic_deliveries()), None)
        yield runs, store, tmp
    mlflow.set_tracking_uri(None)


def test_every_month_is_monitored_in_order(replay):
    runs, _, _ = replay
    assert [pd.Period(m, "M") for m in runs["month"]] == list(MONITORED_MONTHS)
    assert (runs["labelled"] <= runs["orders"]).all()
    assert runs["drift_share"].between(0, 1).all()
    assert runs["drift_report"].str.match(r"runs:/\w+/drift_report\.html$").all()


def test_each_month_is_scored_by_the_pair_live_when_it_began(replay):
    from mlflow import MlflowClient

    runs, _, _ = replay
    client = MlflowClient()
    for row in runs.itertuples():
        version = client.get_model_version(registry.CLASSIFIER_NAME, row.champion_version)
        assert pd.Timestamp(version.tags["serving_from"]) <= pd.Timestamp(row.month)
        assert pd.Timestamp(version.tags["label_cutoff"]) <= pd.Timestamp(row.month)


def test_every_challenger_has_a_recorded_gate_decision(replay):
    from mlflow import MlflowClient

    runs, _, _ = replay
    assert runs["challenger_version"].notna().all()
    client = MlflowClient()
    for row in runs.itertuples():
        version = client.get_model_version(registry.CLASSIFIER_NAME, row.challenger_version)
        assert version.tags["gate"] == ("promoted" if row.gate_passed else "rejected")
        judged = version
        if row.gate_passed:
            judged = client.get_model_version(
                registry.CLASSIFIER_NAME, version.tags["validated_by"]
            )
            assert judged.tags["gate"] == "passed"
        # The fit the gate judged learned nothing that happened during the month.
        assert pd.Timestamp(judged.tags["label_cutoff"]) <= pd.Timestamp(row.month)


def test_simulation_never_touches_the_api_models(replay):
    from mlflow import MlflowClient

    names = {model.name for model in MlflowClient().search_registered_models()}
    assert names == {registry.CLASSIFIER_NAME, registry.REGRESSOR_NAME}
    bootstrap = MlflowClient().get_model_version(registry.CLASSIFIER_NAME, "1")
    assert bootstrap.tags["serving_from"] == SIMULATION_START.date().isoformat()
    assert CHAMPION_ALIAS in MlflowClient().get_registered_model(registry.CLASSIFIER_NAME).aliases


def test_each_drift_report_is_an_artifact_of_its_evaluation_run(replay):
    import mlflow

    runs, _, tmp = replay
    for row in runs.itertuples():
        local = mlflow.artifacts.download_artifacts(row.drift_report, dst_path=str(tmp / "dl"))
        assert Path(local).stat().st_size > 0


def test_report_lists_every_month(replay):
    runs, store, tmp = replay
    path = write_report(runs, store.load_slices(None), tmp / "docs" / "monitoramento.md",
                        date(2026, 1, 1))  # fmt: skip
    text = path.read_text(encoding="utf-8")
    assert "| 2018-08 |" in text
    assert "forced by the test" in text
