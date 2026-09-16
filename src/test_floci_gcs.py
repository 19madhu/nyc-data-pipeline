from google.cloud import storage
from google.auth.credentials import AnonymousCredentials

# Point the client at our local floci-gcp emulator instead of real GCP
client = storage.Client(
    project="floci-local",
    credentials=AnonymousCredentials(),
    client_options={"api_endpoint": "http://localhost:4588"}
)

# Create a test bucket
bucket_name = "nyc311-test-bucket"
bucket = client.create_bucket(bucket_name)
print(f"Bucket created: {bucket.name}")

# Upload a tiny test file
blob = bucket.blob("hello.txt")
blob.upload_from_string("Hello from floci-gcp!")
print("File uploaded successfully")

# Read it back to confirm
downloaded = blob.download_as_text()
print(f"Downloaded content: {downloaded}")