"""Idempotent download of the Olist dataset from Kaggle."""

import logging
import os
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Protocol

from olist_platform.ingestion.sources import KAGGLE_DATASET, SOURCES

logger = logging.getLogger(__name__)


class KaggleClient(Protocol):
    """Subset of ``KaggleApi`` used here, so tests can inject a fake."""

    def dataset_download_files(
        self,
        dataset: str,
        path: str | None = None,
        force: bool = False,
        quiet: bool = True,
        unzip: bool = False,
    ) -> None: ...


def default_client() -> KaggleClient:
    """Authenticated Kaggle client (accepts KAGGLE_USERNAME/KAGGLE_KEY or KAGGLE_API_TOKEN)."""
    # Lazy import: importing ``kaggle`` authenticates at once, so .env must be loaded first.
    from kaggle.api.kaggle_api_extended import KaggleApi

    api = KaggleApi()
    api.authenticate()
    return api


def missing_files(landing_dir: Path) -> list[str]:
    """Source files not yet present in ``landing_dir``."""
    return [s.file_name for s in SOURCES if not (landing_dir / s.file_name).is_file()]


def download_dataset(
    landing_dir: Path,
    client_factory: Callable[[], KaggleClient] = default_client,
    force: bool = False,
) -> bool:
    """Download and unzip the dataset unless every file is already there.

    Returns True when a download happened.
    """
    missing = missing_files(landing_dir)
    if not missing and not force:
        logger.info(
            "All %d source files already in %s; skipping download", len(SOURCES), landing_dir
        )
        return False

    logger.info("Downloading %s into %s (missing: %s)", KAGGLE_DATASET, landing_dir, missing)
    # Unzip into a scratch dir and move files only when complete, so an interrupted download never
    # leaves a truncated CSV that would later pass the "file exists" check.
    staging_dir = landing_dir / ".download"
    shutil.rmtree(staging_dir, ignore_errors=True)
    staging_dir.mkdir(parents=True)
    try:
        client_factory().dataset_download_files(
            KAGGLE_DATASET, path=str(staging_dir), force=True, quiet=True, unzip=True
        )
        not_downloaded = missing_files(staging_dir)
        if not_downloaded:
            raise FileNotFoundError(f"Download finished but files are missing: {not_downloaded}")
        for source in SOURCES:
            os.replace(staging_dir / source.file_name, landing_dir / source.file_name)
    finally:
        shutil.rmtree(staging_dir, ignore_errors=True)
    return True
