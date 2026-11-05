"""Olist pipeline: download from Kaggle, load every CSV into ``raw``, check it and run dbt."""

from datetime import datetime

from airflow.sdk import dag, task


@dag(
    dag_id="olist_ingestion",
    schedule=None,
    start_date=datetime(2026, 1, 1),
    catchup=False,
    # Each run truncates raw and rebuilds the marts; two at once would see half-done state.
    max_active_runs=1,
    tags=["olist", "ingestion", "dbt"],
    doc_md=__doc__,
)
def olist_ingestion():
    @task
    def download() -> bool:
        from olist_platform.ingestion.pipeline import run_download

        return run_download()

    @task
    def load_raw() -> dict[str, int]:
        # One task, one transaction: raw never mixes two loads and the batch shares one _loaded_at.
        from olist_platform.ingestion.pipeline import run_load

        return {result.table: result.rows for result in run_load()}

    @task
    def quality_checks() -> dict[str, int]:
        from olist_platform.ingestion.pipeline import run_checks

        return run_checks()

    @task
    def dbt_build() -> None:
        # Models and tests in one command: a failing test stops the marts that depend on it.
        from olist_platform.transform.dbt import run_dbt

        run_dbt(["build"])

    download() >> load_raw() >> quality_checks() >> dbt_build()


olist_ingestion()
