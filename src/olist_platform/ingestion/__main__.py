"""Command line entry point: ``python -m olist_platform.ingestion {download,load,check,run}``."""

import argparse
import logging
import sys

from olist_platform.ingestion.pipeline import run_checks, run_download, run_load
from olist_platform.ingestion.quality import DataQualityError
from olist_platform.ingestion.settings import load_dotenv_if_present
from olist_platform.ingestion.sources import SOURCES


def build_parser() -> argparse.ArgumentParser:
    """CLI arguments."""
    parser = argparse.ArgumentParser(prog="python -m olist_platform.ingestion")
    sub = parser.add_subparsers(dest="command", required=True)

    download = sub.add_parser("download", help="download the dataset from Kaggle (idempotent)")
    download.add_argument("--force", action="store_true", help="download even if files exist")

    load = sub.add_parser("load", help="load CSVs into the raw schema")
    load.add_argument(
        "--table", choices=[s.table for s in SOURCES], help="load only this raw table"
    )

    sub.add_parser("check", help="check that every raw table exists and has rows")
    sub.add_parser("run", help="download + load + check")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the requested ingestion step."""
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    load_dotenv_if_present()

    try:
        if args.command in ("download", "run"):
            run_download(force=getattr(args, "force", False))
        if args.command in ("load", "run"):
            run_load(table=getattr(args, "table", None))
        if args.command in ("check", "run"):
            run_checks()
    except DataQualityError as error:
        logging.getLogger(__name__).error("Data quality check failed: %s", error)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
