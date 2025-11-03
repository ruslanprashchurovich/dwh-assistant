import json
import re
import os
import requests


def yandex_gpt_query(user_query):
    """
    Sends a user query to YandexGPT via Yandex Cloud API using an API key.
    Returns a structured response including the model's answer or an error message.

    Parameters
    ----------
    user_query : str
        The user's query in natural language.

    Returns
    -------
    dict
        A dictionary with the processing status, the model's answer,
        and an error description if applicable.
    """
    API_KEY = os.getenv("YANDEX_API_KEY")
    FOLDER_ID = os.getenv("YANDEX_FOLDER_ID")

    if not API_KEY:
        return {
            "status": "failure",
            "answer": "",
            "error": "Missing environment variable: YANDEX_API_KEY",
        }
    if not FOLDER_ID:
        return {
            "status": "failure",
            "answer": "",
            "error": "Missing environment variable: YANDEX_FOLDER_ID",
        }

    model_uri = f"gpt://{FOLDER_ID}/yandexgpt/latest"
    url = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Api-Key {API_KEY}",
        "x-folder-id": f"{FOLDER_ID}",
    }

    data = {
        "modelUri": model_uri,
        "completionOptions": {
            "stream": False,
            "temperature": 0.3,
            "maxTokens": 2000,
        },
        "messages": [
            {
                "role": "system",
                "text": "You are an assistant",
            },
            {
                "role": "user",
                "text": user_query,
            },
        ],
    }

    try:
        response = requests.post(
            url, headers=headers, data=json.dumps(data), timeout=30
        )

        if response.status_code == 200:
            try:
                result = response.json()
                answer_text = result["result"]["alternatives"][0]["message"]["text"]
                return {"status": "success", "answer": answer_text, "error": ""}
            except (KeyError, IndexError, TypeError) as e:
                return {
                    "status": "failure",
                    "answer": "",
                    "error": f"Unexpected response format: {str(e)}",
                }
        else:
            try:
                error_detail = (
                    response.json().get("error", {}).get("message", "Unknown error")
                )
            except Exception:
                error_detail = response.text or f"HTTP {response.status_code}"
            return {
                "status": "failure",
                "answer": "",
                "error": f"API request failed with status {response.status_code}: {error_detail}",
            }

    except requests.exceptions.RequestException as e:
        return {"status": "failure", "answer": "", "error": f"Request failed: {str(e)}"}
    except Exception as e:
        return {
            "status": "failure",
            "answer": "",
            "error": f"Unexpected error: {str(e)}",
        }


def generate_prompt(user_query, schema_data):
    """
    Generates a prompt for LLM, including the database schema and the user query.

    Parameters
    ----------
    user_query : str
        The user's query in natural language.
    schema_data : str
        The database schema in DBML format.

    Returns
    -------
    Tuple[str,str]: system prompt and prompt
    """

    system_prompt = """You are a SQL expert that converts natural language questions to PostgreSQL queries.
You MUST use ONLY the tables and columns from the provided database schema.
If the user's request cannot be answered using the available schema, explain why clearly.

DATABASE SCHEMA (DBML format):
{schema_data}

IMPORTANT NOTES ABOUT THE SCHEMA:
- Table "products" has columns: id, name, description, brand, color, weight, dimensions, rating, merchant_id, price, created_at, category_id
- Table "orders" has columns: id, user_id, status, created_at, total_sum, shipping_address, billing_address, payment_method, payment_status, shipping_carrier_id
- Table "users" has columns: id, full_name, email, username, phone_number, last_login_at, avatar_url, created_at, country_code
- Table "categories" has columns: id, name, parent_category_id
- Table "countries" has columns: id, name
- Table "merchants" has columns: id, country_code, status, merchant_name, address, website_url, phone_number, email, logo_url, created_at
- Table "order_items" has columns: id, order_id, product_id, quantity, price, sum
- Table "shipping_carriers" has columns: id, name, tracking_url

RULES:
1. Use only the tables and columns mentioned above
2. For PostgreSQL syntax use CURRENT_DATE for date operations
3. Use proper JOIN syntax with table aliases
4. If the request is impossible with this schema, explain why

EXAMPLES:

1. User: "Show expensive Nike products"
   SQL: "SELECT * FROM products WHERE brand = 'Nike' AND price > 500;"

2. User: "Find USA customers' orders"
   SQL: "SELECT o.* FROM orders o JOIN users u ON o.user_id = u.id JOIN countries c ON u.country_code = c.id WHERE c.name = 'USA';"

3. User: "Count products per category"
   SQL: "SELECT c.name, COUNT(p.id) FROM categories c LEFT JOIN products p ON c.id = p.category_id GROUP BY c.id, c.name;"

4. User: "How old is Dumbledore?"
   Response: {{"sql": "", "error_description": "Cannot answer - the database contains e-commerce data but no information about Harry Potter characters."}}

Now process this request:""".format(
        schema_data=schema_data
    )

    prompt = """User's request: {user_question}

Return your answer as JSON with exactly these fields:
- "sql": the SQL query (empty string if impossible)
- "error_description": explanation why SQL cannot be generated (empty string if SQL is generated)

Return ONLY the JSON, no other text.

Example of valid response when SQL is possible:
{{"sql": "SELECT * FROM products WHERE price > 100;", "error_description": ""}}

Example of valid response when SQL is NOT possible:
{{"sql": "", "error_description": "The request cannot be converted to SQL because..."}}""".format(
        user_question=user_query
    )

    return system_prompt, prompt


def natural_language_to_sql(user_query, schema_data, debug_mode=False):
    """
    Converts a user query from natural language into an SQL query using LLM.

    Parameters
    ----------
    user_query : str
        The user's query in natural language.
    schema_data : str
        The database schema in DBML format.

    Returns
    -------
    dict
        A dictionary with keys: status, sql, error_description, raw_response
    """
    if debug_mode:
        result_text = llm_debug_answer()
        print("Model response:", result_text)
    else:
        system_prompt, prompt = generate_prompt(user_query, schema_data)
        combined_prompt = f"{system_prompt}\n\n{prompt}"
        llm_response = yandex_gpt_query(combined_prompt)
        raw_response = (
            llm_response.get("answer", "").strip()
            if llm_response["status"] == "success"
            else ""
        )

        if llm_response["status"] == "failure":
            return {
                "status": "failure",
                "sql": "",
                "error_description": f"LLM API error: {llm_response['error']}",
                "raw_response": raw_response,
            }

        answer_text = llm_response["answer"].strip()

        try:
            cleaned_text = re.sub(r"```json\s*|\s*```", "", answer_text)

            json_match = re.search(
                r"\{[^{}]*\{[^{}]*\}[^{}]*\}|\{[^{}]*\}", cleaned_text, re.DOTALL
            )
            if json_match:
                json_str = json_match.group()
                result = json.loads(json_str)

                if "sql" in result and "error_description" in result:
                    sql_query = result["sql"].strip() if result["sql"] else ""
                    if (
                        sql_query
                        and sql_query.startswith('"')
                        and sql_query.endswith('"')
                    ):
                        sql_query = sql_query[1:-1]

                    error_desc = (
                        result["error_description"].strip()
                        if result["error_description"]
                        else ""
                    )

                    if sql_query and not error_desc:
                        return {
                            "status": "success",
                            "sql": sql_query,
                            "error_description": "",
                            "raw_response": answer_text,
                        }
                    else:
                        return {
                            "status": "failure",
                            "sql": "",
                            "error_description": (
                                error_desc
                                if error_desc
                                else "LLM couldn't generate SQL query"
                            ),
                            "raw_response": answer_text,
                        }

            sql_match = re.search(
                r"(SELECT|INSERT|UPDATE|DELETE|CREATE|ALTER|DROP).*?;",
                answer_text,
                re.IGNORECASE | re.DOTALL,
            )
            if sql_match:
                return {
                    "status": "success",
                    "sql": sql_match.group().strip(),
                    "error_description": "",
                    "raw_response": answer_text,
                }

            return {
                "status": "failure",
                "sql": "",
                "error_description": "Failed to parse model response.",
                "raw_response": answer_text,
            }

        except json.JSONDecodeError as e:
            sql_match = re.search(
                r"(SELECT|INSERT|UPDATE|DELETE|CREATE|ALTER|DROP).*?;",
                answer_text,
                re.IGNORECASE | re.DOTALL,
            )
            if sql_match:
                return {
                    "status": "success",
                    "sql": sql_match.group().strip(),
                    "error_description": "",
                    "raw_response": answer_text,
                }

            return {
                "status": "failure",
                "sql": "",
                "error_description": f"Failed to parse model response: {str(e)}",
                "raw_response": answer_text,
            }
        except Exception as e:
            return {
                "status": "failure",
                "sql": "",
                "error_description": f"Unexpected error processing LLM response: {str(e)}",
                "raw_response": answer_text,
            }


def llm_debug_answer():
    sql_text = (
        "SELECT u.full_name, COUNT(o.id) AS order_count, "
        "MAX(o.created_at) AS last_purchase "
        "FROM simulator.karpovexpress_users u "
        "JOIN simulator.karpovexpress_orders o "
        "ON u.id = o.user_id GROUP BY u.full_name "
        "ORDER BY order_count DESC LIMIT 5"
    )

    return f'{{ "sql": "{sql_text}", "error_description": "" }}'
