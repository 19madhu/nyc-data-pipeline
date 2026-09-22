import os

from dotenv import load_dotenv
from langchain_ollama import ChatOllama

load_dotenv()

model_name = os.getenv("OLLAMA_MODEL", "llama3.1")

llm = ChatOllama(model=model_name)
response = llm.invoke("Say hello and confirm LangChain + Ollama are working, in one short sentence.")

print(response.content)