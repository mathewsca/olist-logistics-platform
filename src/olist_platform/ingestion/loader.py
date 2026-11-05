"""Load source CSVs into the raw schema exactly as they came, plus lineage columns."""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import psycopg
from psycopg import sql

from olist_platform.ingestion.quality import (
    DataQualityError,
    check_loaded_count,
    check_source_file,
)
from olist_platform.ingestion.sources import RAW_SCHEMA, SOURCES, Source

logger = logging.getLogger(__name__)

COPY_CHUNK_BYTES = 1 << 20
LINEAGE_COLUMNS = ("_loaded_at", "_source_file")


@dataclass(frozen=True)
class LoadResult:
    """Outcome of loading one source file."""

    table: str
    source_file: str
    rows: int
    loaded_at: datetime


def create_table_statement(source: Source, schema: str) -> sql.Composed:
    """DDL for a raw table: every source column as text, plus lineage columns."""
    source_columns = [
        sql.SQL("{} text").format(sql.Identifier(column)) for column in source.columns
    ]
    lineage_columns = [
        sql.SQL("_loaded_at timestamptz not null"),
        sql.SQL("_source_file text not null"),
    ]
    return sql.SQL("create table if not exists {} ({})").format(
        sql.Identifier(schema, source.table),
        sql.SQL(", ").join(source_columns + lineage_columns),
    )


def set_lineage_defaults_statement(
    source: Source, schema: str, loaded_at: datetime
) -> sql.Composed:
    """Lineage values become column defaults, so COPY can stream the file untouched."""
    return sql.SQL(
        "alter table {} alter column _loaded_at set default {}, "
        "alter column _source_file set default {}"
    ).format(
        sql.Identifier(schema, source.table),
        sql.Literal(loaded_at),
        sql.Literal(source.file_name),
    )


def copy_statement(source: Source, schema: str) -> sql.Composed:
    """COPY that reads the CSV (with header) into the source columns."""
    return sql.SQL(
        "copy {} ({}) from stdin with (format csv, header true, encoding 'UTF8')"
    ).format(
        sql.Identifier(schema, source.table),
        sql.SQL(", ").join(sql.Identifier(column) for column in source.columns),
    )


def ensure_schema(conn: psycopg.Connection, schema: str) -> None:
    """Create the schema if missing, tolerating a concurrent creator."""
    try:
        with conn.transaction():
            conn.execute(sql.SQL("create schema if not exists {}").format(sql.Identifier(schema)))
    except (psycopg.errors.UniqueViolation, psycopg.errors.DuplicateSchema):
        pass


def existing_columns(cur: psycopg.Cursor, source: Source, schema: str) -> tuple[str, ...]:
    """Columns of the raw table in ordinal order."""
    cur.execute(
        "select column_name from information_schema.columns "
        "where table_schema = %s and table_name = %s order by ordinal_position",
        (schema, source.table),
    )
    return tuple(row[0] for row in cur.fetchall())


def reload_table(
    cur: psycopg.Cursor, source: Source, landing_dir: Path, schema: str, loaded_at: datetime
) -> int:
    """Replace the table contents with the file; returns the loaded row count.

    TRUNCATE instead of DROP keeps dependent objects (the dbt staging views) valid. The caller's
    transaction makes the swap atomic: readers wait for the commit and never see a partial load.
    """
    cur.execute(create_table_statement(source, schema))
    expected = (*source.columns, *LINEAGE_COLUMNS)
    actual = existing_columns(cur, source, schema)
    if actual != expected:
        raise DataQualityError(
            f"{schema}.{source.table}: existing columns {list(actual)} differ from the source "
            "spec; drop the table (cascade) to let the loader recreate it"
        )

    cur.execute(sql.SQL("truncate table {}").format(sql.Identifier(schema, source.table)))
    cur.execute(set_lineage_defaults_statement(source, schema, loaded_at))
    with (
        (landing_dir / source.file_name).open("rb") as file,
        cur.copy(copy_statement(source, schema)) as copy,
    ):
        while chunk := file.read(COPY_CHUNK_BYTES):
            copy.write(chunk)
    cur.execute(sql.SQL("select count(*) from {}").format(sql.Identifier(schema, source.table)))
    (loaded_rows,) = cur.fetchone()
    return loaded_rows


def load_sources(
    conn: psycopg.Connection,
    sources: tuple[Source, ...] | list[Source],
    landing_dir: Path,
    schema: str = RAW_SCHEMA,
    loaded_at: datetime | None = None,
) -> list[LoadResult]:
    """Validate every file first, then reload all tables in a single transaction.

    One transaction per batch means raw never mixes tables from two loads, and every table of the
    batch shares the same ``_loaded_at``.
    """
    expected_rows = {source.table: check_source_file(source, landing_dir) for source in sources}
    loaded_at = loaded_at or datetime.now(UTC)
    ensure_schema(conn, schema)

    results = []
    with conn.transaction(), conn.cursor() as cur:
        for source in sources:
            loaded_rows = reload_table(cur, source, landing_dir, schema, loaded_at)
            check_loaded_count(source, expected_rows[source.table], loaded_rows)
            logger.info(
                "Loaded %s.%s: %d rows from %s",
                schema,
                source.table,
                loaded_rows,
                source.file_name,
            )
            results.append(LoadResult(source.table, source.file_name, loaded_rows, loaded_at))
    return results


def load_all(
    conn: psycopg.Connection,
    landing_dir: Path,
    schema: str = RAW_SCHEMA,
    loaded_at: datetime | None = None,
) -> list[LoadResult]:
    """Load every source as one atomic batch."""
    return load_sources(conn, SOURCES, landing_dir, schema, loaded_at)


def table_counts(conn: psycopg.Connection, schema: str = RAW_SCHEMA) -> dict[str, int]:
    """Row count of every raw table, for the post-load check."""
    counts = {}
    with conn.cursor() as cur:
        for source in SOURCES:
            cur.execute(
                sql.SQL("select count(*) from {}").format(sql.Identifier(schema, source.table))
            )
            (counts[source.table],) = cur.fetchone()
    return counts
