from datetime import UTC, datetime

from olist_platform.ingestion.loader import (
    copy_statement,
    create_table_statement,
    set_lineage_defaults_statement,
)
from olist_platform.ingestion.sources import get_source

LOADED_AT = datetime(2026, 10, 15, 12, 0, tzinfo=UTC)


def test_create_table_keeps_source_columns_as_text_and_adds_lineage():
    statement = create_table_statement(get_source("sellers"), "raw").as_string()

    assert statement.startswith('create table if not exists "raw"."sellers" (')
    for column in ("seller_id", "seller_zip_code_prefix", "seller_city", "seller_state"):
        assert f'"{column}" text' in statement
    assert statement.endswith("_loaded_at timestamptz not null, _source_file text not null)")


def test_lineage_defaults_carry_batch_timestamp_and_file_name():
    statement = set_lineage_defaults_statement(get_source("sellers"), "raw", LOADED_AT).as_string()

    assert "set default '2026-10-15 12:00:00+00:00'" in statement
    assert "set default 'olist_sellers_dataset.csv'" in statement


def test_copy_lists_only_source_columns_in_file_order():
    statement = copy_statement(get_source("sellers"), "raw").as_string()

    assert statement == (
        'copy "raw"."sellers" ("seller_id", "seller_zip_code_prefix", "seller_city", '
        "\"seller_state\") from stdin with (format csv, header true, encoding 'UTF8')"
    )
