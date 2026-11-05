"""Data quality checks that fail loudly when a source file or raw table is not as expected."""

import csv
from pathlib import Path

from olist_platform.ingestion.sources import Source


class DataQualityError(Exception):
    """A source file or raw table broke an ingestion contract."""


def inspect_csv(path: Path) -> tuple[list[str], int]:
    """Header and record count (excluding the header) in a single pass.

    ``utf-8-sig`` strips the BOM some Olist files carry. Records are counted with the CSV parser,
    not by lines, because review comments contain quoted line breaks.
    """
    with path.open(encoding="utf-8-sig", newline="") as file:
        reader = csv.reader(file)
        header = next(reader, [])
        return header, sum(1 for _ in reader)


def check_source_file(source: Source, landing_dir: Path) -> int:
    """Validate existence, header and non-emptiness of a source file; return its record count."""
    path = landing_dir / source.file_name
    if not path.is_file():
        raise DataQualityError(f"{source.file_name}: file not found in {landing_dir}")

    header, records = inspect_csv(path)
    if tuple(header) != source.columns:
        missing = sorted(set(source.columns) - set(header))
        unexpected = sorted(set(header) - set(source.columns))
        raise DataQualityError(
            f"{source.file_name}: unexpected header "
            f"(missing={missing}, unexpected={unexpected}, got={header})"
        )

    if records == 0:
        raise DataQualityError(f"{source.file_name}: file has no records")
    return records


def check_loaded_count(source: Source, expected: int, loaded: int) -> None:
    """Ensure every record of the file reached the raw table."""
    if loaded != expected:
        raise DataQualityError(
            f"raw.{source.table}: loaded {loaded} rows but {source.file_name} has {expected}"
        )
