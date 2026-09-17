import os
from dotenv import load_dotenv
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate

from sql_agent_schema import COMPLAINT_ANALYSIS_SCHEMA

load_dotenv()

model_name = os.getenv("OLLAMA_MODEL", "llama3.1")
llm = ChatOllama(model=model_name, temperature=0)

SQL_GENERATION_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are a BigQuery SQL expert. Given a database schema and a question,
write a single valid BigQuery Standard SQL query that answers the question.

Schema:
{schema}

Rules:
- Only generate SELECT statements. Never write INSERT, UPDATE, DELETE, DROP, or any statement that modifies data.
- Only use tables and columns that exist in the schema above.
- Always include a LIMIT clause (max 100 rows) unless the question asks for an aggregate (like COUNT).
- When a question refers to a general category that might span multiple exact values (e.g. "noise complaints" could mean several complaint_type values like 'Noise - Residential', 'Noise - Street/Sidewalk', 'Noise - Vehicle'), use LIKE '%keyword%' instead of an exact match, unless the question names an exact category.
- Return ONLY the SQL query, no explanation, no markdown formatting, no backticks around the whole response."""),
    ("user", "{question}")
])


def generate_sql(question: str) -> str:
    chain = SQL_GENERATION_PROMPT | llm
    response = chain.invoke({"schema": COMPLAINT_ANALYSIS_SCHEMA, "question": question})
    return response.content.strip()


if __name__ == "__main__":
    test_question = "Which boroughs had the most noise complaints?"
    sql = generate_sql(test_question)
    print(f"Question: {test_question}\n")
    print(f"Generated SQL:\n{sql}")