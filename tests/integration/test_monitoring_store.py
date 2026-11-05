"""ml.monitoring_* against the compose Postgres, inside a transaction that is always rolled back."""

from datetime import date

import pandas as pd
import psycopg
import pytest

from olist_platform.ingestion.settings import WarehouseSettings, load_dotenv_if_present
from olist_platform.monitoring import store

pytestmark = pytest.mark.integration

MONTH = date(2018, 4, 1)


@pytest.fixture
def conn():
    load_dotenv_if_present()
    try:
        connection = psycopg.connect(WarehouseSettings.from_env().conninfo())
    except psycopg.OperationalError as error:
        pytest.fail(f"Warehouse not reachable (did you run `make up`?): {error}")
    try:
        yield connection
    finally:
        # Never leaves test rows behind (or erases a real simulation's).
        connection.rollback()
        connection.close()


def record(**overrides) -> dict:
    values = {column: None for column in store.RUN_COLUMNS}
    values.update(
        month=MONTH, evaluated_at=date(2018, 6, 1), champion_version="1",
        champion_label_cutoff=date(2018, 4, 1), orders=100, labelled=90, lift=float("nan"),
    )  # fmt: skip
    return values | overrides


def slices(orders: int) -> pd.DataFrame:
    return pd.DataFrame(
        {"region": ["Sudeste", "Sul"], "orders": [orders, 5], "late_rate": [0.1, 0.0],
         "flagged_rate": [0.2, 0.0], "recall": [0.5, float("nan")], "pr_auc": [0.3, float("nan")]}
    )  # fmt: skip


def test_saving_a_month_twice_replaces_it(conn):
    store.reset(conn)
    store.save_month(conn, record(orders=100), slices(50))
    store.save_month(conn, record(orders=120), slices(60))

    runs = store.load_runs(conn)
    assert len(runs) == 1
    assert runs.loc[0, "orders"] == 120
    assert store.load_slices(conn).set_index("region").loc["Sudeste", "orders"] == 60
    # NaN is stored as NULL, so SQL aggregates skip it instead of returning NaN.
    nulls = conn.execute(
        f"select (select count(*) from {store.RUNS_TABLE} where lift is null),"
        f" (select count(*) from {store.SLICES_TABLE} where pr_auc is null)"
    ).fetchone()
    assert nulls == (1, 1)


def test_gate_outcome_is_recorded_on_the_month(conn):
    store.reset(conn)
    store.save_month(conn, record(), slices(50))
    store.save_gate(conn, MONTH, "2", False, "MAE 6.1 worse than the champion's 6.0")

    run = store.load_runs(conn).iloc[0]
    assert run["challenger_version"] == "2"
    assert not run["gate_passed"]
    assert run["gate_detail"].startswith("MAE")


def test_reevaluating_a_month_keeps_its_gate_outcome(conn):
    store.reset(conn)
    store.save_month(conn, record(orders=100), slices(50))
    store.save_gate(conn, MONTH, "2", True, "promoted")
    store.save_month(conn, record(orders=130), slices(70))

    run = store.load_runs(conn).iloc[0]
    assert run["orders"] == 130
    assert run["challenger_version"] == "2"
    assert run["gate_passed"]


def test_gate_outcome_needs_an_evaluated_month(conn):
    store.reset(conn)
    with pytest.raises(RuntimeError, match="no evaluation"):
        store.save_gate(conn, MONTH, "2", False, "rejected")
