from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator

PROJECT_DIR = "/opt/airflow/project"

default_args = {
    "owner": "maddie",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="nyc311_pipeline",
    description="Ingest, transform, load, and model NYC 311 complaint data",
    default_args=default_args,
    schedule="@daily",
    start_date=datetime(2026, 9, 1),
    catchup=False,
    tags=["nyc311"],
) as dag:

    ingest = BashOperator(
        task_id="ingest_raw_data",
        bash_command=f"cd {PROJECT_DIR} && python src/ingest.py",
    )

    transform = BashOperator(
        task_id="flatten_and_stage",
        bash_command=f"cd {PROJECT_DIR} && python src/transform.py",
    )

    load = BashOperator(
        task_id="load_to_bigquery",
        bash_command=f"cd {PROJECT_DIR} && python src/load_to_bigquery.py",
    )

    dbt_run = BashOperator(
        task_id="dbt_run",
        bash_command=f"cd {PROJECT_DIR}/nyc311_dbt && dbt run",
    )

    dbt_test = BashOperator(
        task_id="dbt_test",
        bash_command=f"cd {PROJECT_DIR}/nyc311_dbt && dbt test",
    )

    ingest >> transform >> load >> dbt_run >> dbt_test