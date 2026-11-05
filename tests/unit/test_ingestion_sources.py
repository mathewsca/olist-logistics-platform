import pytest

from olist_platform.ingestion.sources import SOURCES, get_source


def test_there_are_nine_sources_with_unique_tables_and_files():
    assert len(SOURCES) == 9
    assert len({s.table for s in SOURCES}) == 9
    assert len({s.file_name for s in SOURCES}) == 9


def test_columns_are_unique_and_never_clash_with_lineage_columns():
    for source in SOURCES:
        assert len(set(source.columns)) == len(source.columns), source.table
        assert not {"_loaded_at", "_source_file"} & set(source.columns), source.table


def test_get_source_by_table():
    assert get_source("orders").file_name == "olist_orders_dataset.csv"


def test_get_source_unknown_table():
    with pytest.raises(KeyError, match="Unknown raw table"):
        get_source("nope")
