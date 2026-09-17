import os
import json

from dotenv import load_dotenv
from google.cloud import bigquery
from google.cloud import storage
from google.auth.credentials import AnonymousCredentials

load_dotenv()

ENVIRONMENT = os.getenv("ENVIRONMENT", "local")
GCS_ENDPOINT = os.getenv("GCS_ENDPOINT", "http://localhost:4588")

DATASET_ID = "nyc311"
TABLE_ID = "complaints"

LOADED_FILES_BLOB = "_state/loaded_to_bq.json"


def get_loaded_files(storage_client, bucket_name):
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(LOADED_FILES_BLOB)
    if blob.exists():
        return set(json.loads(blob.download_as_text()))
    return set()


def mark_files_loaded(storage_client, bucket_name, loaded_files):
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(LOADED_FILES_BLOB)
    blob.upload_from_string(json.dumps(list(loaded_files)))

SCHEMA = [
    bigquery.SchemaField("unique_key", "STRING"),
    bigquery.SchemaField("created_date", "TIMESTAMP"),
    bigquery.SchemaField("closed_date", "TIMESTAMP"),
    bigquery.SchemaField("complaint_type", "STRING"),
    bigquery.SchemaField("descriptor", "STRING"),
    bigquery.SchemaField("agency", "STRING"),
    bigquery.SchemaField("borough", "STRING"),
    bigquery.SchemaField("status", "STRING"),
    bigquery.SchemaField("latitude", "FLOAT"),
    bigquery.SchemaField("longitude", "FLOAT"),
]


def get_storage_client():
    if ENVIRONMENT == "production":
        project_id = os.getenv("GCP_PROJECT_ID")
        return storage.Client(project=project_id)
    else:
        return storage.Client(
            project="floci-local",
            credentials=AnonymousCredentials(),
            client_options={"api_endpoint": GCS_ENDPOINT},
        )


def get_bucket_name():
    if ENVIRONMENT == "production":
        return os.getenv("GCS_BUCKET_NAME_PROD")
    return "nyc311-raw-data"


def get_bigquery_client():
    project_id = os.getenv("GCP_PROJECT_ID")
    return bigquery.Client(project=project_id)


def ensure_table_exists(bq_client):
    """Creates the table with partitioning + clustering if it doesn't exist yet.
    Safe to call every run — does nothing if the table's already there."""
    table_ref = f"{bq_client.project}.{DATASET_ID}.{TABLE_ID}"

    try:
        bq_client.get_table(table_ref)
        return  # table already exists, nothing to do
    except Exception:
        pass  # doesn't exist yet, create it below

    table = bigquery.Table(table_ref, schema=SCHEMA)

    # Partition by day, based on created_date — keeps date-filtered queries cheap
    table.time_partitioning = bigquery.TimePartitioning(
        type_=bigquery.TimePartitioningType.DAY,
        field="created_date",
    )

    # Cluster by the columns we expect to filter/group by most often
    table.clustering_fields = ["complaint_type", "borough"]

    bq_client.create_table(table)
    print(f"Created table {table_ref} (partitioned by day on created_date, clustered by complaint_type, borough)")


def load_staged_files(bq_client, storage_client, bucket_name):
    bucket = storage_client.bucket(bucket_name)
    staged_blobs = list(bucket.list_blobs(prefix="staging/"))

    already_loaded = get_loaded_files(storage_client, bucket_name)
    table_ref = f"{bq_client.project}.{DATASET_ID}.{TABLE_ID}"

    job_config = bigquery.LoadJobConfig(
        source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
        schema=SCHEMA,
        write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
    )

    newly_loaded = set()

    for blob in staged_blobs:
        if blob.name in already_loaded:
            continue

        records = json.loads(blob.download_as_text())
        ndjson = "\n".join(json.dumps(r) for r in records)

        load_job = bq_client.load_table_from_file(
            file_obj=__import__("io").StringIO(ndjson),
            destination=table_ref,
            job_config=job_config,
        )
        load_job.result()
        print(f"Loaded {len(records)} records from {blob.name} into BigQuery")
        newly_loaded.add(blob.name)

    if newly_loaded:
        mark_files_loaded(storage_client, bucket_name, already_loaded | newly_loaded)
    else:
        print("No new staged files to load — BigQuery is up to date.")


def main():
    storage_client = get_storage_client()
    bucket_name = get_bucket_name()
    bq_client = get_bigquery_client()

    ensure_table_exists(bq_client)
    load_staged_files(bq_client, storage_client, bucket_name)


if __name__ == "__main__":
    main()