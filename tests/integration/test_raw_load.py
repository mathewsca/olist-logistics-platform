from pathlib import Path

import psycopg
import pytest

from olist_platform.ingestion.loader import load_all, table_counts
from olist_platform.ingestion.pipeline import connect
from olist_platform.ingestion.quality import DataQualityError, inspect_csv
from olist_platform.ingestion.settings import load_dotenv_if_present
from olist_platform.ingestion.sources import SOURCES, get_source

pytestmark = pytest.mark.integration

SCHEMA = "raw_integration_test"


@pytest.fixture
def conn():
    load_dotenv_if_present()
    try:
        connection = connect()
    except psycopg.OperationalError as error:
        pytest.fail(f"Warehouse not reachable (did you run `make up`?): {error}")
    with connection:
        yield connection
        connection.execute(f"drop schema if exists {SCHEMA} cascade")


def test_load_all_matches_file_record_counts(conn, landing_dir: Path):
    results = load_all(conn, landing_dir, schema=SCHEMA)

    expected = {s.table: inspect_csv(landing_dir / s.file_name)[1] for s in SOURCES}
    assert {r.table: r.rows for r in results} == expected
    assert table_counts(conn, SCHEMA) == expected


def test_lineage_columns_are_filled_with_one_timestamp_per_batch(conn, landing_dir: Path):
    results = load_all(conn, landing_dir, schema=SCHEMA)
    (loaded_at,) = {r.loaded_at for r in results}

    for source in SOURCES:
        rows = conn.execute(
            f"select distinct _source_file, _loaded_at from {SCHEMA}.{source.table}"
        ).fetchall()
        assert rows == [(source.file_name, loaded_at)], source.table


def test_values_are_preserved_as_text(conn, landing_dir: Path):
    load_all(conn, landing_dir, schema=SCHEMA)

    message = conn.execute(
        f"select review_comment_message from {SCHEMA}.order_reviews where review_id = 'r1'"
    ).fetchone()[0]
    assert message == "Chegou antes do prazo.\nRecomendo!"

    zip_prefix = conn.execute(
        f"select customer_zip_code_prefix from {SCHEMA}.customers where customer_id = 'c1'"
    ).fetchone()[0]
    assert zip_prefix == "01310"

    delivered = conn.execute(
        f"select order_delivered_customer_date from {SCHEMA}.orders where order_id = 'o2'"
    ).fetchone()[0]
    assert delivered is None


def test_reloading_is_idempotent(conn, landing_dir: Path):
    load_all(conn, landing_dir, schema=SCHEMA)
    first = table_counts(conn, SCHEMA)
    load_all(conn, landing_dir, schema=SCHEMA)
    assert table_counts(conn, SCHEMA) == first


def test_failed_batch_keeps_every_previous_table(conn, landing_dir: Path):
    first = load_all(conn, landing_dir, schema=SCHEMA)
    (first_loaded_at,) = {r.loaded_at for r in first}
    source = get_source("sellers")
    (landing_dir / source.file_name).write_text("seller_id\ns9\n", encoding="utf-8")

    with pytest.raises(DataQualityError, match="unexpected header"):
        load_all(conn, landing_dir, schema=SCHEMA)

    for table in ("customers", "orders", "sellers"):
        stamps = conn.execute(f"select distinct _loaded_at from {SCHEMA}.{table}").fetchall()
        assert stamps == [(first_loaded_at,)], table


def test_reload_keeps_dependent_views_working(conn, landing_dir: Path):
    load_all(conn, landing_dir, schema=SCHEMA)
    conn.execute(f"create view {SCHEMA}.v_orders as select order_id from {SCHEMA}.orders")

    load_all(conn, landing_dir, schema=SCHEMA)
    assert conn.execute(f"select count(*) from {SCHEMA}.v_orders").fetchone()[0] == 2


def test_table_with_unexpected_columns_fails_explicitly(conn, landing_dir: Path):
    conn.execute(f"create schema {SCHEMA}")
    conn.execute(f"create table {SCHEMA}.customers (customer_id text)")

    with pytest.raises(DataQualityError, match="differ from the source spec"):
        load_all(conn, landing_dir, schema=SCHEMA)
