import os
import json
import psycopg2
from psycopg2.extras import RealDictCursor
import pandas as pd


def execute_sql_query(sql_query):
    """
    Executes an SQL query in Postgres database and returns the results in a dictionary.

    Parameters
    ----------
    sql_query : str
        SQL query string.

    Returns
    -------
    dict
        A dictionary with two keys
        - 'result' as a pandas DataFrame containing the query results,
        - 'error' with an error message if the execution failed.
    """
    host = os.getenv("PG_STUDENT_HOST")
    port = os.getenv("PG_STUDENT_PORT")
    dbname = os.getenv("PG_STUDENT_DBNAME")
    user = os.getenv("PG_STUDENT_USER")
    password = os.getenv("PG_STUDENT_PASSWORD")

    env_vars = {
        "PG_STUDENT_HOST": host,
        "PG_STUDENT_PORT": port,
        "PG_STUDENT_DBNAME": dbname,
        "PG_STUDENT_USER": user,
        "PG_STUDENT_PASSWORD": password,
    }
    missing = [name for name, value in env_vars.items() if not value]
    if missing:
        return {
            "result": None,
            "error": f"Missing environment variables: {', '.join(missing)}",
        }

    conn = None
    cursor = None
    try:
        port = int(port)
        conn = psycopg2.connect(
            host=host, port=port, dbname=dbname, user=user, password=password
        )
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute(sql_query)

        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        rows = cursor.fetchall() if cursor.description else []

        df = pd.DataFrame(rows, columns=columns) if columns else pd.DataFrame()

        return {"result": df, "error": None}

    except Exception as e:
        return {"result": None, "error": str(e)}

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def build_dbml_schema() -> str:
    """
    Generates a DBML schema for specified tables
    in a PostgreSQL database schema using a static SQL query.
    This version formats the output as per the provided DBML schema example,
    replacing 'double precision' data type with 'double'
    for dbdiagram.io compatibility.

    Returns
    -------
    str
        DBML schema as a string for the specified tables in the schema.
    """
    tables_json = os.getenv("TABLES", "[]")
    table_names = json.loads(tables_json)
    if not table_names:
        return ""

    safe_table_names = []
    for name in table_names:
        if not name.replace("_", "").replace("-", "").isalnum():
            raise ValueError(f"Invalid table name: {name}")
        safe_table_names.append(name)

    table_names_str = "', '".join(safe_table_names)
    query = f"""
        SELECT 
            table_name, 
            column_name, 
            data_type
        FROM information_schema.columns
        WHERE 
            table_schema = 'public'
            AND table_name IN ('{table_names_str}')
        ORDER BY table_name, ordinal_position;
    """

    result = execute_sql_query(query)

    if result["error"] is not None:
        raise RuntimeError(f"Failed to fetch schema: {result['error']}")

    df = result["result"]

    if df.empty:
        return ""

    def map_type(pg_type):
        pg_type = pg_type.lower()
        if pg_type == "double precision":
            return "double"
        elif pg_type == "integer":
            return "int"
        elif pg_type == "character varying":
            return "varchar"
        elif pg_type == "timestamp without time zone":
            return "timestamp"
        elif pg_type == "timestamp with time zone":
            return "timestamptz"
        elif pg_type == "boolean":
            return "bool"
        elif pg_type == "bigint":
            return "bigint"
        elif pg_type == "smallint":
            return "smallint"
        elif pg_type == "numeric" or pg_type == "decimal":
            return "decimal"
        else:
            return pg_type

    dbml_lines = []
    current_table = None

    for _, row in df.iterrows():
        table = row["table_name"]
        column = row["column_name"]
        dtype = map_type(row["data_type"])

        if table != current_table:
            if current_table is not None:
                dbml_lines.append("}")
            dbml_lines.append(f"Table {table} {{")
            current_table = table

        dbml_lines.append(f"  {column} {dtype}")

    if current_table is not None:
        dbml_lines.append("}")

    return "\n".join(dbml_lines)
