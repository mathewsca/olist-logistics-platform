"""Brazilian number format (1.234,5) for the dashboard and the Markdown report, as in the docs."""

import math
from decimal import Decimal

MISSING = "-"


def format_number(value: float | Decimal | None, decimals: int = 0) -> str:
    """``value`` with ``decimals`` places; missing or NaN (a filter with no reviews) is ``-``."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return MISSING
    formatted = f"{value:,.{decimals}f}"
    return formatted.replace(",", "_").replace(".", ",").replace("_", ".")


def format_value(value: object) -> str:
    """A query result cell for Markdown, keeping the decimals the SQL rounded to."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "sim" if value else "não"
    if isinstance(value, int):
        return format_number(value)
    if isinstance(value, float) and math.isnan(value):
        return ""
    if isinstance(value, Decimal | float):
        return format_number(value, max(0, -Decimal(str(value)).as_tuple().exponent))
    return str(value).replace("|", "\\|")


def format_metric(value: float | None, decimals: int) -> str:
    """A metric for a generated report; missing, NaN or infinite values become ``-``."""
    if value is None or (isinstance(value, float) and (math.isnan(value) or math.isinf(value))):
        return MISSING
    return format_number(value, decimals)


def table_lines(header: list[str], align: list[str], rows: list[list[str]]) -> list[str]:
    """Markdown table as a list of lines (``align`` holds ``---`` or ``--:`` per column)."""
    return [
        "| " + " | ".join(header) + " |",
        "|" + "|".join(align) + "|",
        *("| " + " | ".join(row) + " |" for row in rows),
    ]
