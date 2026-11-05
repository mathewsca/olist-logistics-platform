import re
from decimal import Decimal

import pandas as pd
import pytest

from olist_platform.analytics import datasets
from tests.analytics_data import (
    centroids_frame,
    deliveries_frame,
    monitoring_runs_frame,
    orders_frame,
)


@pytest.fixture
def extract_dir(tmp_path):
    frames = {
        "deliveries": deliveries_frame(),
        "orders": orders_frame(),
        "state_centroids": centroids_frame(),
    }
    datasets.export_parquet(frames, tmp_path)
    return tmp_path


def test_normalize_turns_decimals_into_floats_and_parses_timestamps():
    frame = pd.DataFrame(
        {
            "distance_km": [Decimal("1.5"), None],
            "purchased_at": ["2017-01-05 10:00:00", "2017-01-06 11:00:00"],
            "review_score": [5, None],
        }
    )

    normalized = datasets.normalize(frame)

    assert normalized["distance_km"].dtype == float
    assert pd.api.types.is_datetime64_any_dtype(normalized["purchased_at"])
    assert str(normalized["review_score"].dtype) == "Int64"


def test_parquet_round_trip_keeps_rows_and_dtypes(extract_dir):
    loaded = datasets.load_from_parquet(str(extract_dir))

    assert set(loaded) == set(datasets.DATASETS) | set(datasets.OPTIONAL_DATASETS)
    assert loaded["monitoring_runs"].empty
    pd.testing.assert_frame_equal(loaded["deliveries"], deliveries_frame(), check_dtype=False)
    assert pd.api.types.is_datetime64_any_dtype(loaded["deliveries"]["purchased_at"])


def test_optional_datasets_are_exported_only_when_present(tmp_path):
    frames = {"orders": orders_frame(), "monitoring_runs": pd.DataFrame()}
    assert [p.name for p in datasets.export_parquet(frames, tmp_path)] == ["orders.parquet"]
    frames["monitoring_runs"] = monitoring_runs_frame()
    assert len(datasets.export_parquet(frames, tmp_path)) == 2


def test_parquet_path_works_for_directories_and_urls():
    assert datasets.parquet_path("data/extract", "orders") == "data/extract/orders.parquet"
    assert (
        datasets.parquet_path("https://example.com/download/data-v1/", "orders")
        == "https://example.com/download/data-v1/orders.parquet"
    )


def test_load_datasets_reads_the_parquet_location(monkeypatch, extract_dir):
    monkeypatch.setenv("DASHBOARD_SOURCE", "parquet")
    monkeypatch.setenv("DASHBOARD_PARQUET_LOCATION", str(extract_dir))

    assert len(datasets.load_datasets()["orders"]) == len(orders_frame())


def test_load_datasets_rejects_unknown_sources(monkeypatch):
    monkeypatch.setenv("DASHBOARD_SOURCE", "csv")

    with pytest.raises(ValueError, match="DASHBOARD_SOURCE"):
        datasets.load_datasets()


def test_dataset_queries_read_only_marts():
    for name, sql in datasets.DATASETS.items():
        tables = re.findall(r"\b(?:from|join)\s+([\w.]+)", sql)
        assert tables, name
        assert all(table.startswith("marts.") for table in tables), (name, tables)
