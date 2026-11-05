"""Replay 2018-04..08 as production: monitor each month, retrain on a trigger, gate the challenger.

Bootstrap puts the first pair in production; then, month by month, the champion live at the start
of the month is scored on it (drift + performance). A trigger starts a challenger, promoted only
if it passes the quality gate. Every step runs in the image's ML virtualenv.
"""

from datetime import datetime, timedelta

from airflow.sdk import dag, task

from olist_platform.monitoring import SIMULATED_MONTHS

# A skipped retraining must not skip the next month's evaluation.
AFTER_OPTIONAL_RETRAIN = "none_failed"


@dag(
    dag_id="olist_monitoring_retrain",
    schedule=None,
    start_date=datetime(2026, 1, 1),
    catchup=False,
    # Each run resets the simulation's registry entries and ml.monitoring_* tables.
    max_active_runs=1,
    # A step that hangs (e.g. MLflow stops answering) fails instead of holding the only run slot.
    default_args={"execution_timeout": timedelta(minutes=30)},
    tags=["olist", "mlops", "monitoring"],
    doc_md=__doc__,
)
def olist_monitoring_retrain():
    @task
    def bootstrap() -> dict:
        from olist_platform.monitoring.runner import run_step

        return run_step("bootstrap")

    @task(trigger_rule=AFTER_OPTIONAL_RETRAIN)
    def evaluate(month: str) -> dict:
        from olist_platform.monitoring.runner import run_step

        return run_step("evaluate", month)

    @task.short_circuit(ignore_downstream_trigger_rules=False)
    def needs_retraining(outcome: dict) -> bool:
        return bool(outcome["retrain"])

    @task
    def retrain(month: str) -> dict:
        from olist_platform.monitoring.runner import run_step

        return run_step("retrain", month)

    @task(trigger_rule=AFTER_OPTIONAL_RETRAIN)
    def report() -> dict:
        from olist_platform.monitoring.runner import run_step

        return run_step("report")

    previous = bootstrap()
    for month in SIMULATED_MONTHS:
        suffix = month.replace("-", "_")
        outcome = evaluate.override(task_id=f"evaluate_{suffix}")(month)
        previous >> outcome
        decision = needs_retraining.override(task_id=f"needs_retraining_{suffix}")(outcome)
        retrained = retrain.override(task_id=f"retrain_{suffix}")(month)
        decision >> retrained
        previous = retrained
    previous >> report()


olist_monitoring_retrain()
