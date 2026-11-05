from pathlib import Path

import pytest

from olist_platform.ingestion.quality import (
    DataQualityError,
    check_loaded_count,
    check_source_file,
    inspect_csv,
)
from olist_platform.ingestion.sources import SOURCES, get_source


@pytest.mark.parametrize("source", SOURCES, ids=lambda s: s.table)
def test_every_fixture_passes_the_file_checks(source, landing_dir: Path):
    assert check_source_file(source, landing_dir) > 0


def test_header_ignores_utf8_bom(landing_dir: Path):
    path = landing_dir / "product_category_name_translation.csv"
    assert path.read_bytes().startswith(b"\xef\xbb\xbf")
    header, _ = inspect_csv(path)
    assert header == ["product_category_name", "product_category_name_english"]


def test_quoted_line_breaks_count_as_one_record(landing_dir: Path):
    path = landing_dir / "olist_order_reviews_dataset.csv"
    _, records = inspect_csv(path)
    assert records == 2


def test_missing_file_fails(landing_dir: Path):
    source = get_source("orders")
    (landing_dir / source.file_name).unlink()
    with pytest.raises(DataQualityError, match="file not found"):
        check_source_file(source, landing_dir)


def test_missing_column_fails_and_names_it(landing_dir: Path):
    source = get_source("sellers")
    (landing_dir / source.file_name).write_text(
        "seller_id,seller_zip_code_prefix,seller_city\ns1,13023,campinas\n", encoding="utf-8"
    )
    with pytest.raises(DataQualityError, match=r"missing=\['seller_state'\]"):
        check_source_file(source, landing_dir)


def test_reordered_columns_fail(landing_dir: Path):
    source = get_source("sellers")
    (landing_dir / source.file_name).write_text(
        "seller_zip_code_prefix,seller_id,seller_city,seller_state\n13023,s1,campinas,SP\n",
        encoding="utf-8",
    )
    with pytest.raises(DataQualityError, match="unexpected header"):
        check_source_file(source, landing_dir)


def test_header_only_file_fails(landing_dir: Path):
    source = get_source("sellers")
    (landing_dir / source.file_name).write_text(",".join(source.columns) + "\n", encoding="utf-8")
    with pytest.raises(DataQualityError, match="no records"):
        check_source_file(source, landing_dir)


def test_loaded_count_mismatch_fails():
    with pytest.raises(DataQualityError, match="loaded 1 rows but"):
        check_loaded_count(get_source("orders"), expected=2, loaded=1)
