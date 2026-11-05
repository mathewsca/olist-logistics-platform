"""The training query on the real marts: one row per delivery, seller history without leaks."""

import psycopg
import pytest

from olist_platform.features import RAW_INPUT_COLUMNS, build_features
from olist_platform.ingestion.settings import WarehouseSettings, load_dotenv_if_present
from olist_platform.models.data import WINDOW_END, WINDOW_START, load_from_postgres

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def training():
    load_dotenv_if_present()
    conninfo = WarehouseSettings.from_env().conninfo()
    try:
        conn = psycopg.connect(conninfo)
    except psycopg.OperationalError as error:
        pytest.fail(f"Warehouse not reachable (did you run `make up`?): {error}")
    with conn:
        expected = conn.execute(
            "select count(*) from marts.fct_deliveries"
            " where purchased_at >= %s and purchased_at < %s",
            (WINDOW_START.to_pydatetime(), WINDOW_END.to_pydatetime()),
        ).fetchone()[0]
    return load_from_postgres(conninfo), expected


def test_one_row_per_delivery_in_the_window(training):
    data, expected = training
    assert len(data.rows) == expected
    assert data.rows["order_id"].is_unique


def test_rows_carry_every_raw_input(training):
    data, _ = training
    features = build_features(data.rows)
    assert set(RAW_INPUT_COLUMNS) <= set(data.rows.columns)
    assert len(features) == len(data.rows)


def test_seller_history_never_exceeds_deliveries_before_purchase(training):
    data, _ = training
    sample = data.rows.sample(300, random_state=1)
    events = data.deliveries
    for row in sample.itertuples():
        known = (events["seller_id"] == row.seller_id) & (events["delivered_at"] < row.purchased_at)
        assert row.seller_prior_deliveries == known.sum()
