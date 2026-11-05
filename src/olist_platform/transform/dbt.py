"""Run dbt the same way from the CLI, the Makefile and the Airflow DAG."""

import hashlib
import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_PROJECT_DIR = Path("dbt")
PACKAGE_FILES = ("packages.yml", "package-lock.yml")
PACKAGES_MARKER = Path("dbt_packages") / ".installed-from"


class DbtError(RuntimeError):
    """A dbt command finished with a non-zero exit code."""


def project_dir() -> Path:
    """dbt project directory; it also holds profiles.yml."""
    return Path(os.environ.get("DBT_PROJECT_DIR", DEFAULT_PROJECT_DIR))


def dbt_executable() -> str:
    """Path to the dbt CLI.

    In Airflow, dbt lives in its own virtualenv (``DBT_EXECUTABLE``) to keep its pins away from
    Airflow's; locally, the dbt installed next to the running interpreter wins over the PATH.
    """
    if configured := os.environ.get("DBT_EXECUTABLE"):
        return configured
    scripts_dir = Path(sys.executable).parent
    for name in ("dbt", "dbt.exe"):
        candidate = scripts_dir / name
        if candidate.exists():
            return str(candidate)
    found = shutil.which("dbt")
    if found is None:
        raise DbtError("dbt not found: install the `dbt` extra or set DBT_EXECUTABLE")
    return found


def build_command(args: list[str], executable: str, directory: Path) -> list[str]:
    """Full dbt command line for ``args`` against the project in ``directory``."""
    return [executable, *args, "--project-dir", str(directory), "--profiles-dir", str(directory)]


def packages_fingerprint(directory: Path) -> str:
    """Hash of the package declarations, so any edit to them triggers a new ``dbt deps``."""
    digest = hashlib.sha256()
    for name in PACKAGE_FILES:
        path = directory / name
        digest.update(name.encode())
        digest.update(path.read_bytes() if path.exists() else b"")
    return digest.hexdigest()


def packages_installed(directory: Path) -> bool:
    """Whether ``dbt deps`` has installed the packages currently declared by the project."""
    marker = directory / PACKAGES_MARKER
    return marker.is_file() and marker.read_text().strip() == packages_fingerprint(directory)


def mark_packages_installed(directory: Path) -> None:
    """Record which package declarations the current ``dbt_packages/`` was installed from."""
    marker = directory / PACKAGES_MARKER
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(packages_fingerprint(directory) + "\n", newline="\n")


def run_dbt(args: list[str], directory: Path | None = None) -> None:
    """Run one dbt command, installing the packages first when they are missing or outdated."""
    directory = directory or project_dir()
    executable = dbt_executable()
    commands = [args]
    if args[:1] != ["deps"] and not packages_installed(directory):
        commands.insert(0, ["deps"])

    for command_args in commands:
        command = build_command(command_args, executable, directory)
        logger.info("Running: %s", " ".join(command))
        completed = subprocess.run(command, check=False)
        if completed.returncode != 0:
            raise DbtError(f"dbt {command_args[0]} failed with exit code {completed.returncode}")
        if command_args[:1] == ["deps"]:
            # dbt deps may rewrite package-lock.yml, so the fingerprint is taken after it runs.
            mark_packages_installed(directory)
