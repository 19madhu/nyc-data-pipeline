import os
import json
from datetime import datetime, timezone

import requests
from dotenv import load_dotenv
from google.cloud import storage
from google.auth.credentials import AnonymousCredentials

load_dotenv()

# --- Config ---
SOCRATA_APP_TOKEN = os.getenv("NYC311_APP_TOKEN")
SOCRATA_ENDPOINT = "https://data.cityofnewyork.us/resource/erm2-nwe9.json"  # NYC 311 Service Requests dataset
GCS_ENDPOINT = "http://localhost:4588"
BUCKET_NAME = "nyc311-raw-data"
STATE_FILE_BLOB = "_state/last_run.json"


def get_storage_client():
    """Connects to our local floci-gcp emulator (same code works against real GCP later)."""
    return storage.Client(
        project="floci-local",
        credentials=AnonymousCredentials(),
        client_options={"api_endpoint": GCS_ENDPOINT},
    )


def get_or_create_bucket(client):
    bucket = client.bucket(BUCKET_NAME)
    if not bucket.exists():
        bucket = client.create_bucket(BUCKET_NAME)
        print(f"Created bucket: {BUCKET_NAME}")
    return bucket


def get_last_run_timestamp(bucket):
    """Reads the state file to know where the last run left off.
    If it doesn't exist yet, this is our very first run — go back 7 days as a starting point."""
    blob = bucket.blob(STATE_FILE_BLOB)
    if blob.exists():
        state = json.loads(blob.download_as_text())
        return state["last_run"]
    else:
        # First-ever run: no state yet, so pull a small initial window instead of the entire dataset
        from datetime import timedelta
        default_start = datetime.now(timezone.utc) - timedelta(days=7)
        return default_start.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]


def fetch_new_complaints(since_timestamp):
    """Pulls only records created after `since_timestamp` from the Socrata API."""
    params = {
        "$where": f"created_date > '{since_timestamp}'",
        "$order": "created_date ASC",
        "$limit": 5000,  # cap per run; safe for a portfolio-scale project
    }
    headers = {"X-App-Token": SOCRATA_APP_TOKEN}

    response = requests.get(SOCRATA_ENDPOINT, params=params, headers=headers)
    response.raise_for_status()  # crash loudly on API errors instead of silently failing
    return response.json()


def write_records(bucket, records):
    """Writes this run's pull as its own uniquely-named, timestamped file.
    Never appends/overwrites — this is what makes reruns safe (idempotent)."""
    if not records:
        print("No new records since last run.")
        return

    run_timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    blob_path = f"raw/complaints_{run_timestamp}.json"

    blob = bucket.blob(blob_path)
    blob.upload_from_string(json.dumps(records), content_type="application/json")
    print(f"Wrote {len(records)} records to {blob_path}")


def update_last_run_timestamp(bucket, new_timestamp):
    """Only called AFTER a successful write — so a crash mid-run never corrupts our state."""
    blob = bucket.blob(STATE_FILE_BLOB)
    blob.upload_from_string(json.dumps({"last_run": new_timestamp}))
    print(f"State updated. Last run: {new_timestamp}")


def main():
    client = get_storage_client()
    bucket = get_or_create_bucket(client)

    since = get_last_run_timestamp(bucket)
    print(f"Fetching complaints created after: {since}")

    records = fetch_new_complaints(since)

    if records:
        write_records(bucket, records)
        latest_created_date = records[-1]["created_date"]
        update_last_run_timestamp(bucket, latest_created_date)
    else:
        write_records(bucket, records)  # just logs "no new records"


if __name__ == "__main__":
    main()