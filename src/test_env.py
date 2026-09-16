import os
from dotenv import load_dotenv

load_dotenv()

token = os.getenv("NYC311_APP_TOKEN")

if token:
    print(f"Token loaded successfully. Length: {len(token)} characters.")
else:
    print("Token NOT found — check your .env file.")