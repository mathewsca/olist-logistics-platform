import subprocess
from pathlib import Path

import pytest

from olist_platform.transform import dbt
from olist_platform.transform.__main__ import main


@pytest.fixture
def project(tmp_path: Path) -> Path:
    directory = tmp_path / "dbt"
    directory.mkdir()
    (directory / "packages.yml").write_text("packages: []\n")
    return directory


@pytest.fixture
def calls(monkeypatch: pytest.MonkeyPatch) -> list[list[str]]:
    """Records every dbt command instead of running it."""
    recorded: list[list[str]] = []

    def fake_run(command, check):
        recorded.append(command)
        return subprocess.CompletedProcess(command, returncode=0)

    monkeypatch.setattr(dbt.subprocess, "run", fake_run)
    monkeypatch.setenv("DBT_EXECUTABLE", "dbt-bin")
    return recorded


def install_packages(project: Path) -> None:
    dbt.mark_packages_installed(project)


def test_command_points_project_and_profiles_to_the_same_dir():
    command = dbt.build_command(["build", "--select", "marts"], "dbt", Path("dbt"))
    assert command == [
        "dbt",
        "build",
        "--select",
        "marts",
        "--project-dir",
        "dbt",
        "--profiles-dir",
        "dbt",
    ]


def test_executable_from_env_wins(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("DBT_EXECUTABLE", "/opt/dbt-venv/bin/dbt")
    assert dbt.dbt_executable() == "/opt/dbt-venv/bin/dbt"


def test_project_dir_from_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("DBT_PROJECT_DIR", "/opt/airflow/dbt")
    assert dbt.project_dir() == Path("/opt/airflow/dbt")


def test_installs_packages_before_the_first_build(project: Path, calls: list[list[str]]):
    dbt.run_dbt(["build"], project)
    assert [command[1] for command in calls] == ["deps", "build"]


def test_skips_deps_when_packages_are_installed(project: Path, calls: list[list[str]]):
    install_packages(project)
    dbt.run_dbt(["build"], project)
    assert [command[1] for command in calls] == ["build"]


def test_reinstalls_packages_when_declarations_change(project: Path, calls: list[list[str]]):
    install_packages(project)
    (project / "package-lock.yml").write_text("packages: []\nsha1_hash: changed\n")
    dbt.run_dbt(["build"], project)
    assert [command[1] for command in calls] == ["deps", "build"]


def test_successful_deps_marks_packages_installed(project: Path, calls: list[list[str]]):
    dbt.run_dbt(["deps"], project)
    assert dbt.packages_installed(project)


def test_explicit_deps_runs_once(project: Path, calls: list[list[str]]):
    dbt.run_dbt(["deps"], project)
    assert [command[1] for command in calls] == ["deps"]


def test_failure_raises_with_the_exit_code(project: Path, monkeypatch: pytest.MonkeyPatch):
    install_packages(project)
    monkeypatch.setenv("DBT_EXECUTABLE", "dbt-bin")
    monkeypatch.setattr(
        dbt.subprocess, "run", lambda command, check: subprocess.CompletedProcess(command, 1)
    )
    with pytest.raises(dbt.DbtError, match="dbt build failed with exit code 1"):
        dbt.run_dbt(["build"], project)


def test_cli_without_arguments_prints_usage(capsys: pytest.CaptureFixture[str]):
    assert main([]) == 2
    assert "usage" in capsys.readouterr().out


def test_cli_returns_1_when_dbt_fails(monkeypatch: pytest.MonkeyPatch):
    def failing_run(args):
        raise dbt.DbtError("dbt build failed with exit code 1")

    # The developer's real .env must not leak into the rest of the test session.
    monkeypatch.setattr("olist_platform.transform.__main__.load_dotenv_if_present", lambda: None)
    monkeypatch.setattr("olist_platform.transform.__main__.run_dbt", failing_run)
    assert main(["build"]) == 1
