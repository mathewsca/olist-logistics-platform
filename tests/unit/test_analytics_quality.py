from types import SimpleNamespace

from olist_platform.analytics import quality

SEED_ROWS = [
    ("assert_a", "stg_a", "Problema A", "Mantido"),
    ("assert_b", "stg_b", "Problema B", "Descartado"),
]


class FakeConnection:
    """The seed, an audit table only for ``assert_a`` (12 rows), and every query it received."""

    def __init__(self):
        self.queries: list = []

    def execute(self, query, params=None):
        self.queries.append(query)
        if isinstance(query, str) and query.startswith("select test_name"):
            return SimpleNamespace(fetchall=lambda: SEED_ROWS)
        if params is not None:
            exists = "audit.assert_a" if params[0] == "audit.assert_a" else None
            return SimpleNamespace(fetchone=lambda: (exists,))
        return SimpleNamespace(fetchone=lambda: (12,))


def test_issues_keep_the_seed_order_with_their_violation_counts():
    result = quality.load_data_quality(FakeConnection())

    assert list(result.columns) == quality.QUALITY_COLUMNS
    assert list(result["test_name"]) == ["assert_a", "assert_b"]
    assert result.loc[0, "violations"] == 12
    # A test that never ran has no audit table: unknown, not zero.
    assert result["violations"].isna().tolist() == [False, True]


def test_audit_table_names_are_quoted_identifiers():
    conn = FakeConnection()
    quality.load_data_quality(conn)

    counts = [q for q in conn.queries if not isinstance(q, str)]
    assert len(counts) == 1
    assert "assert_a" in repr(counts[0])
