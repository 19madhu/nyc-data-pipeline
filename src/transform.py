import json
import os

from dotenv import load_dotenv
from google.auth.credentials import AnonymousCredentials
from google.cloud import storage

load_dotenv()

ENVIRONMENT = os.getenv("ENVIRONMENT", "local")
GCS_ENDPOINT = os.getenv("GCS_ENDPOINT", "http://localhost:4588")

# Fields we actually want to keep — a deliberate, documented subset
FIELDS_TO_KEEP = [
    "unique_key", "created_date", "closed_date", "complaint_type",
    "descriptor", "agency", "borough", "status",
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


def flatten_record(record):
    """Takes one raw 311 record, returns a flat, cleaned version.
    Missing fields become None rather than raising an error —
    311 records are inconsistently populated, and a single missing
    field shouldn't crash the whole batch."""
    flat = {field: record.get(field) for field in FIELDS_TO_KEEP}

    location = record.get("location")
    if location and isinstance(location, dict):
        try:
            flat["latitude"] = float(location.get("latitude")) if location.get("latitude") else None
            flat["longitude"] = float(location.get("longitude")) if location.get("longitude") else None
        except (ValueError, TypeError):
            flat["latitude"] = None
            flat["longitude"] = None
    else:
        flat["latitude"] = None
        flat["longitude"] = None

    return flat


def process_raw_files(bucket):
    """Finds raw files that haven't been staged yet, flattens them,
    writes the result to staging/. Uses a simple marker approach:
    a staged file is named after its source raw file, so we can
    tell which raw files still need processing."""
    raw_blobs = list(bucket.list_blobs(prefix="raw/"))
    staged_blobs = {b.name for b in bucket.list_blobs(prefix="staging/")}

    processed_count = 0

    for raw_blob in raw_blobs:
        staged_name = raw_blob.name.replace("raw/", "staging/")

        if staged_name in staged_blobs:
            continue  # already processed — this is what makes reruns idempotent

        raw_data = json.loads(raw_blob.download_as_text())
        flattened = [flatten_record(r) for r in raw_data]

        staged_blob = bucket.blob(staged_name)
        staged_blob.upload_from_string(
            json.dumps(flattened), content_type="application/json"
        )
        print(f"Staged {len(flattened)} records: {raw_blob.name} -> {staged_name}")
        processed_count += 1

    if processed_count == 0:
        print("No new raw files to process — staging is up to date.")


def main():
    client = get_storage_client()
    bucket_name = get_bucket_name()
    bucket = client.bucket(bucket_name)

    process_raw_files(bucket)


if __name__ == "__main__":
    main()