import re
from datetime import date
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

from olist_platform.analytics import formatting, report
from tests.analytics_data import data_quality_frame


class FakeConnection:
    """Answers every query with the same columns and rows, recording the SQL it received."""

    def __init__(self, columns: list[str], rows: list[tuple]):
        self.columns = columns
        self.rows = rows
        self.queries: list[str] = []

    def execute(self, sql: str):
        self.queries.append(sql)
        return SimpleNamespace(
            description=[SimpleNamespace(name=name) for name in self.columns],
            fetchall=lambda: self.rows,
        )


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, ""),
        (True, "sim"),
        (96470, "96.470"),
        (Decimal("6.8"), "6,8"),
        (Decimal("1389"), "1.389"),
        (Decimal("2.46"), "2,46"),
        (1234.5, "1.234,5"),
        (float("nan"), ""),
        ("SP | RJ", "SP \\| RJ"),
    ],
)
def test_format_value_uses_brazilian_format_and_keeps_sql_decimals(value, expected):
    assert formatting.format_value(value) == expected


def test_format_number_rounds_to_the_requested_decimals():
    assert formatting.format_number(12345.678, 1) == "12.345,7"


def test_format_number_shows_missing_values_as_a_dash():
    # e.g. the average score of a filter with no reviewed deliveries.
    assert formatting.format_number(float("nan"), 2) == "-"
    assert formatting.format_number(None) == "-"


def test_markdown_table_right_aligns_numeric_columns():
    table = report.markdown_table(["state", "late_pct"], [("SP", Decimal("4.5")), ("RJ", None)])

    assert table.splitlines() == [
        "| state | late_pct |",
        "|---|--:|",
        "| SP | 4,5 |",
        "| RJ |  |",
    ]


def test_compiled_dir_follows_dbt_target_path(monkeypatch):
    monkeypatch.setenv("DBT_TARGET_PATH", "target_ci")

    assert report.compiled_analyses_dir(Path("dbt")) == Path(
        "dbt/target_ci/compiled/olist/analyses"
    )


def test_write_report_runs_every_analysis_in_order(tmp_path, monkeypatch):
    monkeypatch.delenv("DBT_TARGET_PATH", raising=False)
    compiled = tmp_path / "dbt" / "target" / "compiled" / "olist" / "analyses"
    compiled.mkdir(parents=True)
    for analysis in report.ANALYSES:
        (compiled / f"{analysis.name}.sql").write_text(f"select '{analysis.name}'")
    conn = FakeConnection(["deliveries"], [(10,)])
    monkeypatch.setattr(report, "load_data_quality", lambda conn: data_quality_frame())
    output = tmp_path / "docs" / "analises.md"

    results = report.write_report(conn, tmp_path / "dbt", output, date(2026, 10, 24))

    assert conn.queries == [f"select '{a.name}'" for a in report.ANALYSES]
    assert len(results) == len(report.ANALYSES)
    text = output.read_text(encoding="utf-8")
    assert "executadas em 2026-10-24" in text
    assert "| Problema A | `stg_a` | 12 | Mantido |" in text
    assert "| Problema B | `stg_b` |  | Descartado |" in text
    assert text.count("| deliveries |") == len(report.ANALYSES)
    assert "\r\n" not in output.read_bytes().decode("utf-8")


def test_every_analysis_has_a_sql_file():
    analyses_dir = Path(__file__).parents[2] / "dbt" / "analyses"

    assert {a.name for a in report.ANALYSES} == {p.stem for p in analyses_dir.glob("*.sql")}


def test_numbers_in_descriptions_match_the_sql():
    # Descriptions repeat the cut-offs of the queries (20 routes, 300 deliveries, 180 days...).
    analyses_dir = Path(__file__).parents[2] / "dbt" / "analyses"
    for analysis in report.ANALYSES:
        sql = (analyses_dir / f"{analysis.name}.sql").read_text(encoding="utf-8")
        for number in re.findall(r"\d[\d.]*\d|\d", analysis.description):
            assert number.replace(".", "") in sql, (analysis.name, number)
