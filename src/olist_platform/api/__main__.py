"""Command line entry point: ``python -m olist_platform.api export|serve``."""

import argparse
import logging
import os
import sys
from pathlib import Path

from olist_platform.api.app import DEFAULT_BUNDLE_DIR

DEFAULT_TRACKING_URI = "http://localhost:5000"


def build_parser() -> argparse.ArgumentParser:
    """CLI arguments."""
    parser = argparse.ArgumentParser(prog="python -m olist_platform.api")
    sub = parser.add_subparsers(dest="command", required=True)
    export = sub.add_parser("export", help="copy the champions and lookups into a bundle directory")
    export.add_argument("--out", type=Path, default=DEFAULT_BUNDLE_DIR)
    serve = sub.add_parser("serve", help="run the API with uvicorn")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    return parser


def run_export(out: Path) -> None:
    """Champions from MLflow + zip-prefix coordinates from the marts."""
    from olist_platform.api.bundle import export_bundle
    from olist_platform.ingestion.settings import WarehouseSettings

    tracking_uri = os.environ.get("MLFLOW_TRACKING_URI", DEFAULT_TRACKING_URI)
    metadata = export_bundle(tracking_uri, WarehouseSettings.from_env().conninfo(), out)
    logging.info(
        "Exported %s v%s and %s v%s to %s",
        metadata["classifier"]["name"],
        metadata["classifier"]["version"],
        metadata["regressor"]["name"],
        metadata["regressor"]["version"],
        out,
    )


def main(argv: list[str] | None = None) -> int:
    """Run the requested command."""
    from olist_platform.ingestion.settings import load_dotenv_if_present

    args = build_parser().parse_args(argv)
    # MLflow prints emoji; a cp1252 Windows console (or a redirect) would crash.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    load_dotenv_if_present()
    if args.command == "export":
        run_export(args.out)
    else:
        import uvicorn

        uvicorn.run(
            "olist_platform.api.app:create_app", factory=True, host=args.host, port=args.port
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
