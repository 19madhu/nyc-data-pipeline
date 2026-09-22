import json
import os
import time
from datetime import datetime, timedelta, timezone

import requests
from dotenv import load_dotenv
from google.auth.credentials import AnonymousCredentials
from google.cloud import storage

load_dotenv()

# --- Config ---
SOCRATA_APP_TOKEN = os.getenv("NYC311_APP_TOKEN")
SOCRATA_ENDPOINT = "https://data.cityofnewyork.us/resource/erm2-nwe9.json"
GCS_ENDPOINT = os.getenv("GCS_ENDPOINT", "http://localhost:4588")
ENVIRONMENT = os.getenv("ENVIRONMENT", "local")
BUCKET_NAME = os.getenv("GCS_BUCKET_NAME_PROD") if ENVIRONMENT == "production" else "nyc311-raw-data"
STATE_FILE_BLOB = "_state/last_run.json"

FIRST_RUN_LOOKBACK_DAYS = 7  # named, deliberate default — not a magic number
MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = 5  # doubles each retry: 5s, 10s, 20s


def get_storage_client():
    """Switches between local Floci emulator and real GCP based on ENVIRONMENT.
    Same code, same SDK calls, zero changes needed elsewhere in the script —
    only the client configuration differs."""
    environment = os.getenv("ENVIRONMENT", "local")

    if environment == "production":
        # Real GCP — authenticates using the service account key file
        project_id = os.getenv("GCP_PROJECT_ID")
        return storage.Client(project=project_id)
    else:
        # Local Floci emulator — no real credentials needed
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
    blob = bucket.blob(STATE_FILE_BLOB)
    if blob.exists():
        state = json.loads(blob.download_as_text())
        return state["last_run"]
    else:
        default_start = datetime.now(timezone.utc) - timedelta(days=FIRST_RUN_LOOKBACK_DAYS)
        return default_start.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]


def fetch_new_complaints(since_timestamp):
    """Pulls records created after `since_timestamp`.
    Retries on transient failures (network errors, timeouts, 5xx server errors)
    with exponential backoff — but does NOT retry on 4xx errors (bad request,
    bad token), since retrying a broken request just fails the same way again."""
    params = {
        "$where": f"created_date > '{since_timestamp}'",
        "$order": "created_date ASC",
        "$limit": 5000,
    }
    headers = {"X-App-Token": SOCRATA_APP_TOKEN}

    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.get(SOCRATA_ENDPOINT, params=params, headers=headers, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            status = e.response.status_code
            if 400 <= status < 500:
                # Client error (bad token, bad query) — retrying won't help, fail fast
                print(f"Client error {status}, not retrying: {e}")
                raise
            last_error = e
        except requests.exceptions.RequestException as e:
            # Network error, timeout, connection issue — worth retrying
            last_error = e

        wait = RETRY_BACKOFF_SECONDS * (2 ** (attempt - 1))
        print(f"Attempt {attempt}/{MAX_RETRIES} failed ({last_error}). Retrying in {wait}s...")
        time.sleep(wait)

    raise RuntimeError(f"Failed to fetch data after {MAX_RETRIES} attempts. Last error: {last_error}")


def write_records(bucket, records):
    if not records:
        print("No new records since last run.")
        return

    run_timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    blob_path = f"raw/complaints_{run_timestamp}.json"

    blob = bucket.blob(blob_path)
    blob.upload_from_string(json.dumps(records), content_type="application/json")
    print(f"Wrote {len(records)} records to {blob_path}")


def update_last_run_timestamp(bucket, new_timestamp):
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
        write_records(bucket, records)


if __name__ == "__main__":
    main()