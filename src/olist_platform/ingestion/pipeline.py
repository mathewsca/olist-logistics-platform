"""Ingestion steps shared by the CLI and the Airflow DAG."""

import logging
from pathlib import Path

import psycopg

from olist_platform.ingestion.download import download_dataset
from olist_platform.ingestion.loader import LoadResult, load_all, load_sources, table_counts
from olist_platform.ingestion.quality import DataQualityError
from olist_platform.ingestion.settings import WarehouseSettings, landing_dir
from olist_platform.ingestion.sources import RAW_SCHEMA, get_source

logger = logging.getLogger(__name__)


def connect(settings: WarehouseSettings | None = None) -> psycopg.Connection:
    """Open a connection to the warehouse."""
    settings = settings or WarehouseSettings.from_env()
    return psycopg.connect(settings.conninfo(), autocommit=True)


def run_download(directory: Path | None = None, force: bool = False) -> bool:
    """Download step."""
    return download_dataset(directory or landing_dir(), force=force)


def run_load(table: str | None = None, directory: Path | None = None) -> list[LoadResult]:
    """Load every raw table as one atomic batch, or only ``table``."""
    directory = directory or landing_dir()
    with connect() as conn:
        if table is None:
            return load_all(conn, directory)
        return load_sources(conn, [get_source(table)], directory)


def run_checks(schema: str = RAW_SCHEMA) -> dict[str, int]:
    """Post-load check: every raw table exists and has rows. Logs the counts."""
    with connect() as conn:
        try:
            counts = table_counts(conn, schema)
        except psycopg.errors.UndefinedTable as error:
            raise DataQualityError(f"Raw table missing: {error}") from error

    for table, rows in counts.items():
        logger.info("%s.%s: %d rows", schema, table, rows)
    empty = [table for table, rows in counts.items() if rows == 0]
    if empty:
        raise DataQualityError(f"Empty raw tables: {empty}")
    return counts
