import os
from typing import TypedDict, Optional
from dotenv import load_dotenv
from langgraph.graph import StateGraph, END
from google.cloud import bigquery

from text_to_sql import generate_sql
from sql_validator import validate_sql, SQLValidationError

load_dotenv()


class AgentState(TypedDict):
    question: str
    previous_question: Optional[str]
    previous_sql: Optional[str]
    sql: Optional[str]
    validation_error: Optional[str]
    retry_count: int
    rows: Optional[list]
    final_error: Optional[str]


def get_bigquery_client():
    project_id = os.getenv("GCP_PROJECT_ID")
    return bigquery.Client(project=project_id)


# --- Nodes ---

def generate_sql_node(state: AgentState) -> dict:
    """Generates SQL from the question. Includes the previous turn's question
    and SQL as context (for follow-up questions like 'what about the Bronx?').
    If this is a retry (validation_error is set), includes that error too."""
    question = state["question"]

    if state.get("previous_question") and state.get("previous_sql"):
        question = (
            f"Previous question: {state['previous_question']}\n"
            f"Previous SQL: {state['previous_sql']}\n\n"
            f"New question (may refer back to the previous one): {state['question']}"
        )

    if state.get("validation_error"):
        question = (
            f"{question}\n\n"
            f"Note: a previous attempt produced invalid SQL for this reason: "
            f"{state['validation_error']}. Please correct it."
        )

    sql = generate_sql(question)
    return {"sql": sql}


def validate_sql_node(state: AgentState) -> dict:
    """Validates the generated SQL. Clears any prior validation error on success,
    or records the new error for the retry path."""
    try:
        validated = validate_sql(state["sql"])
        return {"sql": validated, "validation_error": None}
    except SQLValidationError as e:
        return {"validation_error": str(e)}


def route_after_validation(state: AgentState) -> str:
    """Decides where to go after validation: proceed to execution,
    retry generation once, or give up after too many attempts."""
    if state.get("validation_error") is None:
        return "execute"
    if state["retry_count"] >= 1:
        return "give_up"
    return "retry"


def increment_retry_node(state: AgentState) -> dict:
    return {"retry_count": state["retry_count"] + 1}


def execute_query_node(state: AgentState) -> dict:
    """Runs the validated SQL against real BigQuery."""
    try:
        client = get_bigquery_client()
        query_job = client.query(state["sql"])
        rows = [dict(row) for row in query_job.result()]
        return {"rows": rows}
    except Exception as e:
        return {"final_error": f"Query execution failed: {e}"}


def give_up_node(state: AgentState) -> dict:
    return {"final_error": f"Could not produce valid SQL after retry: {state['validation_error']}"}


# --- Build the graph ---

def build_graph():
    graph = StateGraph(AgentState)

    graph.add_node("generate", generate_sql_node)
    graph.add_node("validate", validate_sql_node)
    graph.add_node("increment_retry", increment_retry_node)
    graph.add_node("execute", execute_query_node)
    graph.add_node("give_up", give_up_node)

    graph.set_entry_point("generate")
    graph.add_edge("generate", "validate")

    graph.add_conditional_edges(
        "validate",
        route_after_validation,
        {
            "execute": "execute",
            "retry": "increment_retry",
            "give_up": "give_up",
        },
    )

    graph.add_edge("increment_retry", "generate")
    graph.add_edge("execute", END)
    graph.add_edge("give_up", END)

    return graph.compile()


sql_graph = build_graph()


def answer_question(question: str, previous_question: str = None, previous_sql: str = None) -> dict:
    initial_state = {
        "question": question,
        "previous_question": previous_question,
        "previous_sql": previous_sql,
        "sql": None,
        "validation_error": None,
        "retry_count": 0,
        "rows": None,
        "final_error": None,
    }
    result = sql_graph.invoke(initial_state)
    return result


if __name__ == "__main__":
    print("NYC 311 SQL Assistant (LangGraph) — ask a question, or type 'quit' to exit.\n")

    last_question = None
    last_sql = None

    while True:
        question = input("Question: ").strip()
        if question.lower() in ("quit", "exit"):
            print("Goodbye!")
            break
        if not question:
            continue

        result = answer_question(question, previous_question=last_question, previous_sql=last_sql)

        print(f"\nSQL: {result.get('sql')}\n")

        if result.get("final_error"):
            print(f"ERROR: {result['final_error']}\n")
        else:
            print("Results:")
            for row in result.get("rows", []):
                print(f"  {row}")
            print()

        # Remember this turn for the next question, but only if it succeeded —
        # a failed turn shouldn't poison the next question's context
        if not result.get("final_error"):
            last_question = result.get("question")
            last_sql = result.get("sql")