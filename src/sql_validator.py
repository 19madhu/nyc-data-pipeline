import re

ALLOWED_TABLE = "maddie19.nyc311_dbt.complaint_resolution_analysis"

FORBIDDEN_KEYWORDS = [
    "INSERT", "UPDATE", "DELETE", "DROP", "ALTER",
    "TRUNCATE", "CREATE", "MERGE", "GRANT", "REVOKE",
]

MAX_ROW_LIMIT = 100


class SQLValidationError(Exception):
    """Raised when generated SQL fails a safety check."""
    pass


def validate_sql(sql: str) -> str:
    """Validates generated SQL against safety rules.
    Returns the (possibly modified) SQL if it passes.
    Raises SQLValidationError if it fails."""

    cleaned = sql.strip().rstrip(";")

    # Rule 1: must start with SELECT
    if not re.match(r"^\s*SELECT\b", cleaned, re.IGNORECASE):
        raise SQLValidationError("Only SELECT statements are allowed.")

    # Rule 2: no forbidden keywords anywhere in the query
    upper_sql = cleaned.upper()
    for keyword in FORBIDDEN_KEYWORDS:
        if re.search(rf"\b{keyword}\b", upper_sql):
            raise SQLValidationError(f"Forbidden keyword detected: {keyword}")

    # Rule 3: no multiple statements (semicolon-separated chaining)
    if ";" in sql.strip().rstrip(";"):
        raise SQLValidationError("Multiple statements are not allowed.")

    # Rule 4: must only reference the authorized table
    # (checks the table name appears; doesn't guarantee no OTHER tables are referenced,
    # so this is a basic check, not exhaustive — documented limitation)
    if ALLOWED_TABLE.split(".")[-1] not in cleaned:
        raise SQLValidationError(f"Query must reference the authorized table: {ALLOWED_TABLE}")

    # Rule 5: must have a LIMIT, unless it's a pure aggregate query (no GROUP BY, single row expected)
    has_limit = re.search(r"\bLIMIT\s+\d+", upper_sql)
    has_group_by = re.search(r"\bGROUP\s+BY\b", upper_sql)

    if not has_limit:
        # Only allow missing LIMIT if this is a genuine scalar aggregate query —
        # i.e. the SELECT clause consists ONLY of aggregate functions (COUNT, SUM,
        # AVG, MIN, MAX), nothing else. Anything else (raw columns, no GROUP BY,
        # no LIMIT) can return unbounded rows and must be rejected.
        select_clause_match = re.search(r"SELECT\s+(.*?)\s+FROM", cleaned, re.IGNORECASE | re.DOTALL)
        is_scalar_aggregate = False

        if select_clause_match:
            select_items = select_clause_match.group(1).split(",")
            is_scalar_aggregate = all(
                re.match(r"^\s*(COUNT|SUM|AVG|MIN|MAX)\s*\(.*\)(\s+AS\s+\w+)?\s*$", item.strip(), re.IGNORECASE)
                for item in select_items
            )

        if not is_scalar_aggregate:
            raise SQLValidationError("Query must include a LIMIT clause (only pure aggregate queries like COUNT(*) may omit it).")
    else:
        # Enforce the max row limit even if the model set a higher one
        limit_value = int(has_limit.group().split()[-1])
        if limit_value > MAX_ROW_LIMIT:
            cleaned = re.sub(r"LIMIT\s+\d+", f"LIMIT {MAX_ROW_LIMIT}", cleaned, flags=re.IGNORECASE)

    return cleaned


if __name__ == "__main__":
    # Quick manual tests
    test_cases = [
        "SELECT borough FROM maddie19.nyc311_dbt.complaint_resolution_analysis GROUP BY borough LIMIT 100",
        "DROP TABLE maddie19.nyc311_dbt.complaint_resolution_analysis",
        "SELECT * FROM maddie19.nyc311_dbt.complaint_resolution_analysis; DROP TABLE users",
        "SELECT COUNT(*) FROM maddie19.nyc311_dbt.complaint_resolution_analysis",
        "SELECT borough FROM other_table LIMIT 10",
        "SELECT unique_key, borough FROM maddie19.nyc311_dbt.complaint_resolution_analysis WHERE borough = 'BRONX'",
        
    ]

    for sql in test_cases:
        print(f"\nSQL: {sql}")
        try:
            result = validate_sql(sql)
            print(f"  VALID: {result}")
        except SQLValidationError as e:
            print(f"  REJECTED: {e}")
            