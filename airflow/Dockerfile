FROM apache/airflow:3.3.2-python3.12

# Dependencies are installed from the metadata alone (the package __init__ holds the version), so
# editing src/ does not reinstall them on every `make up --build`.
COPY --chown=airflow:root pyproject.toml README.md /opt/olist/
COPY --chown=airflow:root src/olist_platform/__init__.py /opt/olist/src/olist_platform/
# Pinning apache-airflow in the same install keeps pip from up/downgrading it to satisfy our deps.
RUN pip install --no-cache-dir "apache-airflow==${AIRFLOW_VERSION}" "/opt/olist[ingestion]"

# dbt gets its own virtualenv: its pins (protobuf, jinja2, ...) must not fight Airflow's.
USER root
RUN python -m venv /opt/dbt-venv \
    && /opt/dbt-venv/bin/pip install --no-cache-dir "/opt/olist[dbt]" \
    && chown -R airflow:root /opt/dbt-venv
# LightGBM links against OpenMP at runtime (the Airflow base image does not ship it).
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*
# Same reason for the monitoring stack: Evidently pins pandas below 3 and LightGBM/MLflow bring
# their own pins. The DAG runs it through olist_platform.monitoring.runner (OLIST_ML_PYTHON).
RUN python -m venv /opt/ml-venv \
    && /opt/ml-venv/bin/pip install --no-cache-dir "/opt/olist[monitoring]" \
    && chown -R airflow:root /opt/ml-venv
USER airflow

COPY --chown=airflow:root src /opt/olist/src
# Both interpreters get the full package, so the image also works without the src/ mount.
RUN pip install --no-cache-dir --no-deps /opt/olist \
    && /opt/ml-venv/bin/pip install --no-cache-dir --no-deps /opt/olist
