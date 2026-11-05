"""Command line entry point: ``python -m olist_platform.models train``."""

import argparse
import logging
import os
import sys
from datetime import date
from pathlib import Path

from olist_platform.ingestion.settings import WarehouseSettings, load_dotenv_if_present

logger = logging.getLogger(__name__)

DEFAULT_TRACKING_URI = "http://localhost:5000"


def build_parser() -> argparse.ArgumentParser:
    """CLI arguments."""
    parser = argparse.ArgumentParser(prog="python -m olist_platform.models")
    sub = parser.add_subparsers(dest="command", required=True)
    train = sub.add_parser("train", help="train, evaluate and register the models")
    train.add_argument("--report", type=Path, help="report path (default: docs/modelagem.md)")
    return parser


def run_train(report: Path | None) -> None:
    """Train from the marts, track in MLflow and write the report."""
    from olist_platform.models.data import load_from_postgres
    from olist_platform.models.report import REPORT_PATH, write_report
    from olist_platform.models.train import run_training

    tracking_uri = os.environ.get("MLFLOW_TRACKING_URI", DEFAULT_TRACKING_URI)
    data = load_from_postgres(WarehouseSettings.from_env().conninfo())
    logger.info("Loaded %d modelling rows, %d deliveries", len(data.rows), len(data.deliveries))
    outcome = run_training(data, tracking_uri)
    path = write_report(outcome, report or REPORT_PATH, date.today())
    logger.info("Wrote %s", path)


def main(argv: list[str] | None = None) -> int:
    """Run the requested command."""
    args = build_parser().parse_args(argv)
    # MLflow prints emoji when a run ends; a cp1252 Windows console (or a redirect) would crash.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    load_dotenv_if_present()
    run_train(args.report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
