"""Command line entry point: ``python -m olist_platform.analytics {report,extract}``."""

import argparse
import logging
import sys
from datetime import date
from pathlib import Path

from olist_platform.ingestion.settings import WarehouseSettings, load_dotenv_if_present

logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    """CLI arguments."""
    parser = argparse.ArgumentParser(prog="python -m olist_platform.analytics")
    sub = parser.add_subparsers(dest="command", required=True)

    report = sub.add_parser("report", help="compile and run dbt/analyses, write docs/analises.md")
    report.add_argument("--output", type=Path, help="report path (default: docs/analises.md)")

    extract = sub.add_parser("extract", help="export the dashboard datasets to Parquet")
    extract.add_argument("--output", type=Path, help="directory (default: data/extract)")
    return parser


def run_report(output: Path | None) -> None:
    """Compile the analyses with dbt and write their results."""
    import psycopg

    from olist_platform.analytics.report import REPORT_PATH, write_report
    from olist_platform.transform.dbt import project_dir, run_dbt

    run_dbt(["compile", "--select", "path:analyses"])
    output = output or REPORT_PATH
    with psycopg.connect(WarehouseSettings.from_env().conninfo()) as conn:
        results = write_report(conn, project_dir(), output, date.today())
    logger.info("Wrote %d analyses to %s", len(results), output)


def run_extract(output: Path | None) -> None:
    """Export the marts the dashboard reads to Parquet."""
    from olist_platform.analytics.datasets import (
        DEFAULT_EXTRACT_DIR,
        export_parquet,
        load_from_postgres,
    )

    frames = load_from_postgres(WarehouseSettings.from_env().conninfo())
    for path in export_parquet(frames, output or DEFAULT_EXTRACT_DIR):
        logger.info("Wrote %s (%d KB)", path, path.stat().st_size // 1024)


def main(argv: list[str] | None = None) -> int:
    """Run the requested command."""
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    load_dotenv_if_present()

    from olist_platform.transform.dbt import DbtError

    try:
        if args.command == "report":
            run_report(args.output)
        else:
            run_extract(args.output)
    except DbtError as error:
        logger.error("%s", error)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
