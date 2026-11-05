"""Command line entry point: ``python -m olist_platform.transform <dbt args>``.

Loads ``.env`` (dbt itself does not) and forwards the arguments to dbt, e.g.
``python -m olist_platform.transform build --select marts``.
"""

import logging
import sys

from olist_platform.ingestion.settings import load_dotenv_if_present
from olist_platform.transform.dbt import DbtError, run_dbt


def main(argv: list[str] | None = None) -> int:
    """Run dbt with the given arguments."""
    args = sys.argv[1:] if argv is None else argv
    if not args:
        print("usage: python -m olist_platform.transform <dbt command> [options]")
        return 2
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    load_dotenv_if_present()
    try:
        run_dbt(args)
    except DbtError as error:
        logging.getLogger(__name__).error("%s", error)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
