import json
import os
from datetime import datetime, timezone

from dotenv import load_dotenv
from google.auth.credentials import AnonymousCredentials
from google.cloud import storage
from kafka import KafkaProducer

load_dotenv()

GCS_ENDPOINT = os.getenv("GCS_ENDPOINT", "http://localhost:4588")
TOPIC_NAME = "priority-complaints"

PRIORITY_KEYWORDS = ["Water", "Heat", "Gas", "Structural"]


def get_broker_address() -> str:
    with open("kafka_broker.txt") as f:
        return f.read().strip()


def get_storage_client():
    environment = os.getenv("ENVIRONMENT", "local")
    if environment == "production":
        return storage.Client(project=os.getenv("GCP_PROJECT_ID"))
    return storage.Client(
        project="floci-local",
        credentials=AnonymousCredentials(),
        client_options={"api_endpoint": GCS_ENDPOINT},
    )


def get_bucket_name() -> str:
    environment = os.getenv("ENVIRONMENT", "local")
    if environment == "production":
        return os.getenv("GCS_BUCKET_NAME_PROD")
    return "nyc311-raw-data"


def is_priority(complaint: dict) -> bool:
    complaint_type = complaint.get("complaint_type", "")
    return any(keyword in complaint_type for keyword in PRIORITY_KEYWORDS)


def get_producer() -> KafkaProducer:
    broker = get_broker_address()
    return KafkaProducer(
        bootstrap_servers=broker,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    )


def publish_priority_complaints():
    """Reads the most recent staged batch from GCS, filters for
    priority complaint types, and publishes each one to Kafka."""
    storage_client = get_storage_client()
    bucket = storage_client.bucket(get_bucket_name())

    staged_blobs = sorted(
        bucket.list_blobs(prefix="staging/"),
        key=lambda b: b.name,
        reverse=True,
    )

    if not staged_blobs:
        print("No staged files found.")
        return

    latest_blob = staged_blobs[0]
    print(f"Reading latest staged file: {latest_blob.name}")

    records = json.loads(latest_blob.download_as_text())
    priority_records = [r for r in records if is_priority(r)]

    print(f"Found {len(priority_records)} priority complaints out of {len(records)} total.")

    if not priority_records:
        print("No priority complaints to publish.")
        return

    producer = get_producer()

    for record in priority_records:
        event = {
            **record,
            "published_at": datetime.now(timezone.utc).isoformat(),
        }
        producer.send(TOPIC_NAME, value=event)

    producer.flush()  # ensures all messages are actually sent before exiting
    print(f"Published {len(priority_records)} priority complaints to topic '{TOPIC_NAME}'.")


if __name__ == "__main__":
    publish_priority_complaints()