import os

from dotenv import load_dotenv
from google.auth.credentials import AnonymousCredentials
from google.cloud import storage

load_dotenv()

ENVIRONMENT = os.getenv("ENVIRONMENT", "local")
GCS_ENDPOINT = "http://localhost:4588"

def get_storage_client():
    if ENVIRONMENT == "production":
        return storage.Client(project=os.getenv("GCP_PROJECT_ID"))
    return storage.Client(
        project="floci-local",
        credentials=AnonymousCredentials(),
        client_options={"api_endpoint": GCS_ENDPOINT},
    )

def get_bucket_name():
    if ENVIRONMENT == "production":
        return os.getenv("GCS_BUCKET_NAME_PROD")
    return "nyc311-raw-data"

client = get_storage_client()
bucket = client.bucket(get_bucket_name())
blob = bucket.blob("_state/loaded_to_bq.json")

if blob.exists():
    blob.delete()
    print("Deleted load-state file — next run will reload everything fresh.")
else:
    print("No state file found — nothing to reset.")