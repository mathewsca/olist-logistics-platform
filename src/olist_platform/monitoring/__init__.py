"""Data drift and model performance monitoring."""

# Plain strings (no pandas) so the Airflow DAG can lay out one task per month when it is parsed.
SIMULATED_MONTHS = ("2018-04", "2018-05", "2018-06", "2018-07", "2018-08")
