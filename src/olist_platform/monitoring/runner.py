"""Run a monitoring step in the ML virtualenv and return its JSON outcome (standard library only).

Airflow's interpreter does not carry the ML stack (Evidently pins pandas below 3), so the DAG
calls these functions, which start ``python -m olist_platform.monitoring`` with ``OLIST_ML_PYTHON``.
"""

import json
import logging
import os
import subprocess
import sys
import tempfile

logger = logging.getLogger(__name__)


class MonitoringStepError(RuntimeError):
    """A monitoring step finished with a non-zero exit code."""


def build_command(step: str, month: str | None = None) -> list[str]:
    """Command line of one step, run by the configured interpreter."""
    command = [os.environ.get("OLIST_ML_PYTHON", sys.executable), "-m", "olist_platform.monitoring"]
    command.append(step)
    if month is not None:
        command += ["--month", month]
    return command


def parse_outcome(stdout: str) -> dict:
    """The step's outcome: the last JSON line it printed (MLflow may print before it)."""
    for line in reversed(stdout.strip().splitlines()):
        if line.startswith("{"):
            return json.loads(line)
    raise MonitoringStepError("The step printed no JSON outcome")


def run_step(step: str, month: str | None = None) -> dict:
    """Run ``step`` from ``OLIST_PROJECT_DIR`` (paths in reports are relative to it).

    The step's logs (stderr) are relayed line by line while it runs; the Airflow task's
    ``execution_timeout`` bounds a step that hangs.
    """
    command = build_command(step, month)
    logger.info("Running %s", " ".join(command))
    with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as stdout:
        process = subprocess.Popen(
            command,
            cwd=os.environ.get("OLIST_PROJECT_DIR", "."),
            stdout=stdout,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        try:
            for line in process.stderr:
                logger.info("%s", line.rstrip())
            returncode = process.wait()
        finally:
            if process.poll() is None:
                process.kill()
        if returncode != 0:
            raise MonitoringStepError(f"{step} exited with code {returncode}")
        stdout.seek(0)
        outcome = parse_outcome(stdout.read())
    logger.info("Outcome: %s", outcome)
    return outcome
