import os

import ollama
from dotenv import load_dotenv

load_dotenv()

model = os.getenv("OLLAMA_MODEL", "llama3.1")

response = ollama.chat(
    model=model,
    messages=[
        {"role": "user", "content": "Say hello and confirm you're working, in one short sentence."}
    ]
)

print(response["message"]["content"])