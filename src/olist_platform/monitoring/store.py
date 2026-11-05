"""One row per monitored month in ``ml.monitoring_runs``, plus its region slices."""

import pandas as pd

RUNS_TABLE = "ml.monitoring_runs"
SLICES_TABLE = "ml.monitoring_region_slices"

DDL = f"""
create table if not exists {RUNS_TABLE} (
    month date primary key,
    evaluated_at date not null,
    champion_version text not null,
    champion_label_cutoff date not null,
    orders integer not null,
    labelled integer not null,
    late_rate double precision,
    pr_auc double precision,
    lift double precision,
    recall double precision,
    flagged_rate double precision,
    mae double precision,
    bias double precision,
    validation_lift double precision,
    validation_mae double precision,
    drift_share double precision,
    drifted_features integer,
    drift_report text,
    retrain_reasons text,
    challenger_version text,
    gate_passed boolean,
    gate_detail text,
    run_at timestamptz not null default now()
);
create table if not exists {SLICES_TABLE} (
    month date not null references {RUNS_TABLE} (month) on delete cascade,
    region text not null,
    orders integer not null,
    late_rate double precision,
    flagged_rate double precision,
    recall double precision,
    pr_auc double precision,
    primary key (month, region)
);
"""

RUN_COLUMNS = (
    "month", "evaluated_at", "champion_version", "champion_label_cutoff", "orders", "labelled",
    "late_rate", "pr_auc", "lift", "recall", "flagged_rate", "mae", "bias", "validation_lift",
    "validation_mae", "drift_share", "drifted_features", "drift_report", "retrain_reasons",
)  # fmt: skip
SLICE_COLUMNS = ("region", "orders", "late_rate", "flagged_rate", "recall", "pr_auc")


def _clean(value):
    # psycopg sends NaN as a float NaN, which Postgres stores but SQL averages then propagate.
    return None if isinstance(value, float) and value != value else value


def reset(conn) -> None:
    """Drop every monitored month (a replay starts over)."""
    conn.execute(DDL)
    conn.execute(f"truncate {RUNS_TABLE} cascade")


def save_month(conn, record: dict, slices: pd.DataFrame) -> None:
    """Upsert the month's evaluation and replace its slices in one transaction.

    The gate columns are left alone: re-running a month's evaluation keeps the outcome of the
    retraining it already triggered (the challenger stays in MLflow either way).
    """
    updates = ", ".join(f"{column} = excluded.{column}" for column in RUN_COLUMNS[1:])
    with conn.transaction():
        conn.execute(DDL)
        conn.execute(
            f"insert into {RUNS_TABLE} ({', '.join(RUN_COLUMNS)}, run_at)"
            f" values ({', '.join(['%s'] * len(RUN_COLUMNS))}, now())"
            f" on conflict (month) do update set {updates}, run_at = now()",
            [_clean(record.get(column)) for column in RUN_COLUMNS],
        )
        conn.execute(f"delete from {SLICES_TABLE} where month = %s", (record["month"],))
        for row in slices.itertuples(index=False):
            conn.execute(
                f"insert into {SLICES_TABLE} (month, {', '.join(SLICE_COLUMNS)})"
                f" values (%s, {', '.join(['%s'] * len(SLICE_COLUMNS))})",
                [record["month"], *(_clean(getattr(row, c)) for c in SLICE_COLUMNS)],
            )


def save_gate(conn, month, challenger_version: str, passed: bool, detail: str) -> None:
    """Record the retraining outcome on the month that triggered it (which must be evaluated)."""
    cursor = conn.execute(
        f"update {RUNS_TABLE} set challenger_version = %s, gate_passed = %s, gate_detail = %s"
        " where month = %s",
        (challenger_version, passed, detail, month),
    )
    if cursor.rowcount != 1:
        raise RuntimeError(f"{month} has no evaluation to attach the gate outcome to")


def _frame(conn, sql: str) -> pd.DataFrame:
    cursor = conn.execute(sql)
    return pd.DataFrame(cursor.fetchall(), columns=[c.name for c in cursor.description])


def load_runs(conn) -> pd.DataFrame:
    """Every monitored month, oldest first."""
    conn.execute(DDL)
    return _frame(conn, f"select * from {RUNS_TABLE} order by month")


def load_slices(conn) -> pd.DataFrame:
    """Region slices of every monitored month."""
    conn.execute(DDL)
    return _frame(conn, f"select * from {SLICES_TABLE} order by month, region")
