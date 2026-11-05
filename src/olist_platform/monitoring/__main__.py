"""Command line entry point: ``python -m olist_platform.monitoring {simulate,bootstrap,...}``.

``simulate`` replays every month at once (``make monitor``); the other commands are the steps of
the Airflow DAG. Each step prints its outcome as one JSON line on stdout (logs go to stderr).
"""

import argparse
import json
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
    parser = argparse.ArgumentParser(prog="python -m olist_platform.monitoring")
    sub = parser.add_subparsers(dest="command", required=True)
    for name, help_text in (
        ("simulate", "replay every month and write the report"),
        ("report", "write the report from the stored months"),
    ):
        command = sub.add_parser(name, help=help_text)
        command.add_argument("--report", type=Path, help="default: docs/monitoramento.md")
    sub.add_parser("bootstrap", help="start a replay: reset and put the first pair in production")
    for name, help_text in (
        ("evaluate", "score one month, measure drift and performance, decide on retraining"),
        ("retrain", "fit a challenger without the month and run the quality gate"),
    ):
        command = sub.add_parser(name, help=help_text)
        command.add_argument("--month", required=True, help="YYYY-MM, one of the simulated months")
    return parser


def _load_data():
    from olist_platform.models.data import load_from_postgres

    data = load_from_postgres(WarehouseSettings.from_env().conninfo())
    logger.info("Loaded %d modelling rows, %d deliveries", len(data.rows), len(data.deliveries))
    return data


def _write_report(conn, path: Path | None) -> Path:
    from olist_platform.monitoring import store
    from olist_platform.monitoring.report import REPORT_PATH, write_report

    return write_report(
        store.load_runs(conn), store.load_slices(conn), path or REPORT_PATH, date.today()
    )


def run(args: argparse.Namespace) -> dict:
    """Execute one command; returns what it decided."""
    import mlflow
    import psycopg

    from olist_platform.monitoring import simulation
    from olist_platform.monitoring.windows import parse_month

    mlflow.set_tracking_uri(os.environ.get("MLFLOW_TRACKING_URI", DEFAULT_TRACKING_URI))
    month = parse_month(args.month) if getattr(args, "month", None) else None
    with psycopg.connect(WarehouseSettings.from_env().conninfo()) as conn:
        if args.command == "report":
            return {"report": _write_report(conn, args.report).as_posix()}
        data = _load_data()
        if args.command == "simulate":
            runs = simulation.simulate(data, conn)
            conn.commit()
            path = _write_report(conn, args.report)
            return {"months": len(runs), "report": path.as_posix()}
        if args.command == "bootstrap":
            simulation.store.reset(conn)
            return {"versions": simulation.bootstrap(data)}
        if args.command == "evaluate":
            return simulation.evaluate_month(data, month, conn)
        return simulation.retrain_and_gate(data, month, conn)


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
    print(json.dumps(run(args), default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
