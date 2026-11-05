import sys

import pytest

from olist_platform.monitoring import SIMULATED_MONTHS
from olist_platform.monitoring.__main__ import build_parser
from olist_platform.monitoring.runner import (
    MonitoringStepError,
    build_command,
    parse_outcome,
    run_step,
)
from olist_platform.monitoring.windows import MONITORED_MONTHS


def test_dag_months_match_the_simulation_calendar():
    assert [str(month) for month in MONITORED_MONTHS] == list(SIMULATED_MONTHS)


def test_command_uses_the_ml_interpreter(monkeypatch):
    monkeypatch.setenv("OLIST_ML_PYTHON", "/opt/ml-venv/bin/python")
    assert build_command("evaluate", "2018-04") == [
        "/opt/ml-venv/bin/python", "-m", "olist_platform.monitoring", "evaluate",
        "--month", "2018-04",
    ]  # fmt: skip


def test_every_dag_step_is_a_cli_command():
    parser = build_parser()
    for step, month in (("bootstrap", None), ("evaluate", "2018-04"), ("retrain", "2018-04"),
                        ("report", None)):  # fmt: skip
        args = parser.parse_args(build_command(step, month)[3:])
        assert args.command == step


def test_outcome_is_the_last_json_line():
    stdout = 'View run at http://mlflow\n{"month": "2018-04", "retrain": true}\n'
    assert parse_outcome(stdout) == {"month": "2018-04", "retrain": True}


def test_missing_outcome_fails():
    with pytest.raises(MonitoringStepError, match="no JSON"):
        parse_outcome("nothing here\n")


def test_failed_step_raises(monkeypatch, tmp_path):
    script = tmp_path / "olist_platform" / "monitoring"
    script.mkdir(parents=True)
    (tmp_path / "olist_platform" / "__init__.py").write_text("")
    (script / "__init__.py").write_text("")
    (script / "__main__.py").write_text("import sys\nsys.exit(3)\n")
    monkeypatch.setenv("OLIST_ML_PYTHON", sys.executable)
    monkeypatch.setenv("OLIST_PROJECT_DIR", str(tmp_path))
    with pytest.raises(MonitoringStepError, match="code 3"):
        run_step("bootstrap")
