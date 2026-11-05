"""Known data issues (dbt seed ``data_issues``) and the violations their tests left in audit."""

import pandas as pd

SEED_TABLE = "marts.data_issues"
AUDIT_SCHEMA = "audit"
QUALITY_COLUMNS = ["test_name", "model", "issue", "treatment", "violations"]


def violation_count(conn, test_name: str) -> int | None:
    """Rows the test stored in ``audit``; None when it has not run yet."""
    from psycopg import sql

    exists = conn.execute("select to_regclass(%s)", (f"{AUDIT_SCHEMA}.{test_name}",)).fetchone()[0]
    if exists is None:
        return None
    query = sql.SQL("select count(*) from {}").format(sql.Identifier(AUDIT_SCHEMA, test_name))
    return conn.execute(query).fetchone()[0]


def load_data_quality(conn) -> pd.DataFrame:
    """One row per known issue with its violation count, in the seed's order."""
    cursor = conn.execute(f"select test_name, model, issue, treatment from {SEED_TABLE}")
    issues = pd.DataFrame(cursor.fetchall(), columns=QUALITY_COLUMNS[:-1])
    counts = [violation_count(conn, name) for name in issues["test_name"]]
    return issues.assign(violations=pd.array(counts, dtype="Int64"))
