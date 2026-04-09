"""
LLM service with multi-provider support (YandexGPT, OpenAI/ChatGPT, Anthropic/Claude).
Each provider implements the BaseLLMProvider interface.
Conversation history is passed to providers for contextual follow-up queries.
"""

import json
import re
import os
from abc import ABC, abstractmethod

from openai import AsyncOpenAI
from anthropic import AsyncAnthropic


# ============================================================
#  ABSTRACT BASE PROVIDER
# ============================================================

class BaseLLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    async def query(
        self,
        system_prompt: str,
        user_message: str,
        conversation_history: list[dict] | None = None,
        temperature: float = 0.3,
    ) -> dict:
        """
        Send a query to the LLM.

        Parameters
        ----------
        system_prompt : str
            System instructions (schema, rules, format).
        user_message : str
            Current user message.
        conversation_history : list[dict] | None
            Previous messages as [{"role": "user"/"assistant", "content": str}, ...].
        temperature : float
            Sampling temperature.

        Returns
        -------
        dict with keys: status ("success"/"failure"), answer (str), error (str)
        """
        pass


# ============================================================
#  YANDEX GPT PROVIDER
# ============================================================

class YandexGPTProvider(BaseLLMProvider):
    """YandexGPT via Yandex Cloud OpenAI-compatible API (responses.create)."""

    async def query(
        self,
        system_prompt: str,
        user_message: str,
        conversation_history: list[dict] | None = None,
        temperature: float = 0.3,
    ) -> dict:
        api_key = os.getenv("YANDEX_CLOUD_API_KEY")
        folder = os.getenv("YANDEX_CLOUD_FOLDER")
        model = os.getenv("YANDEX_CLOUD_MODEL")

        if not api_key:
            return _failure("Missing environment variable: YANDEX_CLOUD_API_KEY")
        if not folder:
            return _failure("Missing environment variable: YANDEX_CLOUD_FOLDER")
        if not model:
            return _failure("Missing environment variable: YANDEX_CLOUD_MODEL")

        model_uri = f"gpt://{folder}/{model}"

        client = AsyncOpenAI(
            api_key=api_key,
            base_url="https://ai.api.cloud.yandex.net/v1",
            project=folder,
        )

        # Build combined prompt with conversation history
        combined = system_prompt
        if conversation_history:
            combined += "\n\nPrevious conversation:\n"
            for msg in conversation_history:
                role_label = "User" if msg["role"] == "user" else "Assistant"
                combined += f"{role_label}: {msg['content']}\n"
        combined += f"\n\n{user_message}"

        try:
            response = await client.responses.create(
                model=model_uri,
                temperature=temperature,
                input=combined,
                max_output_tokens=500,
            )

            if response.error is not None:
                return _failure(f"API error: {response.error}")
            if response.status != "completed":
                return _failure(f"Response status: {response.status}")
            if not response.output:
                return _failure("Empty response output")

            try:
                first_message = response.output[0]
                if hasattr(first_message, "content") and first_message.content:
                    first_content = first_message.content[0]
                    answer_text = getattr(first_content, "text", "")
                else:
                    answer_text = ""
            except (IndexError, AttributeError, TypeError) as e:
                return _failure(
                    f"Failed to parse response structure: {type(e).__name__}: {e}"
                )

            if not answer_text:
                return _failure("Empty answer from model")

            return {"status": "success", "answer": answer_text, "error": ""}

        except Exception as e:
            return _failure(f"Unexpected error: {type(e).__name__}: {e}")


# ============================================================
#  OPENAI (ChatGPT) PROVIDER
# ============================================================

class OpenAIProvider(BaseLLMProvider):
    """OpenAI ChatGPT via official API (chat.completions.create)."""

    async def query(
        self,
        system_prompt: str,
        user_message: str,
        conversation_history: list[dict] | None = None,
        temperature: float = 0.3,
    ) -> dict:
        api_key = os.getenv("OPENAI_API_KEY")
        model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

        if not api_key:
            return _failure("Missing environment variable: OPENAI_API_KEY")

        client = AsyncOpenAI(api_key=api_key)

        # Build messages array
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        if conversation_history:
            messages.extend(conversation_history)
        messages.append({"role": "user", "content": user_message})

        try:
            response = await client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=500,
            )

            answer_text = response.choices[0].message.content or ""
            if not answer_text.strip():
                return _failure("Empty answer from model")

            return {"status": "success", "answer": answer_text.strip(), "error": ""}

        except Exception as e:
            return _failure(f"Unexpected error: {type(e).__name__}: {e}")


# ============================================================
#  ANTHROPIC (Claude) PROVIDER
# ============================================================

class AnthropicProvider(BaseLLMProvider):
    """Anthropic Claude via official API (messages.create)."""

    async def query(
        self,
        system_prompt: str,
        user_message: str,
        conversation_history: list[dict] | None = None,
        temperature: float = 0.3,
    ) -> dict:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        model = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")

        if not api_key:
            return _failure("Missing environment variable: ANTHROPIC_API_KEY")

        client = AsyncAnthropic(api_key=api_key)

        # Build messages (system is passed separately in Anthropic API)
        messages = []
        if conversation_history:
            messages.extend(conversation_history)
        messages.append({"role": "user", "content": user_message})

        try:
            kwargs = dict(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=500,
            )
            if system_prompt:
                kwargs["system"] = system_prompt
            response = await client.messages.create(**kwargs)

            answer_text = ""
            if response.content:
                for block in response.content:
                    if hasattr(block, "text"):
                        answer_text += block.text

            if not answer_text.strip():
                return _failure("Empty answer from model")

            return {"status": "success", "answer": answer_text.strip(), "error": ""}

        except Exception as e:
            return _failure(f"Unexpected error: {type(e).__name__}: {e}")


# ============================================================
#  PROVIDER FACTORY
# ============================================================

PROVIDERS: dict[str, type[BaseLLMProvider]] = {
    "yandex": YandexGPTProvider,
    "openai": OpenAIProvider,
    "anthropic": AnthropicProvider,
}


def get_provider(name: str) -> BaseLLMProvider:
    """
    Get an LLM provider instance by name.

    Parameters
    ----------
    name : str
        Provider identifier: "yandex", "openai", or "anthropic".

    Returns
    -------
    BaseLLMProvider instance.

    Raises
    ------
    ValueError if provider name is unknown.
    """
    cls = PROVIDERS.get(name)
    if cls is None:
        available = ", ".join(PROVIDERS.keys())
        raise ValueError(f"Unknown LLM provider: '{name}'. Available: {available}")
    return cls()


def get_default_provider_name() -> str:
    """Return the default provider name from LLM_PROVIDER env var."""
    provider = os.getenv("LLM_PROVIDER", "yandex").lower().strip()
    if provider not in PROVIDERS:
        return "yandex"
    return provider


# ============================================================
#  HELPER
# ============================================================

def _failure(error: str) -> dict:
    return {"status": "failure", "answer": "", "error": error}


# ============================================================
#  PROMPT GENERATION
# ============================================================

def generate_system_prompt(schema_data: str) -> str:
    """
    Generate the system prompt with DB schema, rules, examples, and output format.
    """
    return """You are a SQL expert that converts natural language questions to PostgreSQL queries.
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
   Response: {{"sql": "SELECT * FROM products WHERE brand = 'Nike' AND price > 500;", "error_description": ""}}

2. User: "Find USA customers' orders"
   Response: {{"sql": "SELECT o.* FROM orders o JOIN users u ON o.user_id = u.id JOIN countries c ON u.country_code = c.id WHERE c.name = 'USA';", "error_description": ""}}

3. User: "Count products per category"
   Response: {{"sql": "SELECT c.name, COUNT(p.id) FROM categories c LEFT JOIN products p ON c.id = p.category_id GROUP BY c.id, c.name;", "error_description": ""}}

4. User: "How old is Dumbledore?"
   Response: {{"sql": "", "error_description": "Cannot answer - the database contains e-commerce data but no information about Harry Potter characters."}}

RESPONSE FORMAT:
Return ONLY a JSON object with exactly these fields:
- "sql": the SQL query (empty string if impossible)
- "error_description": explanation why SQL cannot be generated (empty string if SQL is generated)

Example valid response: {{"sql": "SELECT * FROM products WHERE price > 100;", "error_description": ""}}""".format(
        schema_data=schema_data
    )


def format_user_message(user_query: str) -> str:
    """Format the user query for sending to LLM."""
    return f"User's request: {user_query}"


# ============================================================
#  RESPONSE PARSING
# ============================================================

def parse_llm_response(answer_text: str) -> dict:
    """
    Parse LLM response text into a structured result.
    Tries JSON parsing first, falls back to raw SQL regex extraction.

    Returns
    -------
    dict with keys: status, sql, error_description, raw_response
    """
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
                            error_desc if error_desc
                            else "LLM couldn't generate SQL query"
                        ),
                        "raw_response": answer_text,
                    }

        # Fallback: try to find raw SQL in the response
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
            "error_description": f"Failed to parse model response: {e}",
            "raw_response": answer_text,
        }
    except Exception as e:
        return {
            "status": "failure",
            "sql": "",
            "error_description": f"Unexpected error processing LLM response: {e}",
            "raw_response": answer_text,
        }


# ============================================================
#  MAIN ENTRY POINT
# ============================================================

def is_system_prompt_enabled() -> bool:
    """Check if system prompt is enabled via USE_SYSTEM_PROMPT env var."""
    return os.getenv("USE_SYSTEM_PROMPT", "0").strip().lower() in ("1", "true", "yes")


async def natural_language_to_sql(
    user_query: str,
    schema_data: str,
    provider_name: str = "yandex",
    conversation_history: list[dict] | None = None,
    debug_mode: bool = False,
) -> dict:
    """
    Convert a natural language query to SQL using the specified LLM provider.

    Parameters
    ----------
    user_query : str
        The user's question in natural language.
    schema_data : str
        Database schema in DBML format.
    provider_name : str
        LLM provider to use: "yandex", "openai", or "anthropic".
    conversation_history : list[dict] | None
        Previous conversation messages for context.
    debug_mode : bool
        If True, return a hardcoded SQL query for testing.

    Returns
    -------
    dict with keys: status, sql, error_description, raw_response
    """
    if debug_mode:
        result_text = llm_debug_answer()
        print("Model response:", result_text)
        try:
            result = json.loads(result_text)
            return {
                "status": "success",
                "sql": result.get("sql", ""),
                "error_description": result.get("error_description", ""),
                "raw_response": result_text,
            }
        except json.JSONDecodeError:
            return {
                "status": "failure",
                "sql": "",
                "error_description": "Failed to parse debug response",
                "raw_response": result_text,
            }

    # Get the provider
    try:
        provider = get_provider(provider_name)
    except ValueError as e:
        return {
            "status": "failure",
            "sql": "",
            "error_description": str(e),
            "raw_response": "",
        }

    # Generate prompts
    if is_system_prompt_enabled():
        system_prompt = generate_system_prompt(schema_data)
    else:
        system_prompt = ""
    user_message = format_user_message(user_query)

    # Call LLM
    llm_response = await provider.query(
        system_prompt=system_prompt,
        user_message=user_message,
        conversation_history=conversation_history,
    )

    if llm_response["status"] == "failure":
        return {
            "status": "failure",
            "sql": "",
            "error_description": f"LLM API error: {llm_response['error']}",
            "raw_response": llm_response.get("answer", ""),
        }

    # Parse the response
    answer_text = llm_response["answer"].strip()
    return parse_llm_response(answer_text)


# ============================================================
#  DEBUG HELPER
# ============================================================

def llm_debug_answer() -> str:
    sql_text = (
        "SELECT u.full_name, COUNT(o.id) AS order_count, "
        "MAX(o.created_at) AS last_purchase "
        "FROM simulator.karpovexpress_users u "
        "JOIN simulator.karpovexpress_orders o "
        "ON u.id = o.user_id GROUP BY u.full_name "
        "ORDER BY order_count DESC LIMIT 5"
    )
    return f'{{ "sql": "{sql_text}", "error_description": "" }}'
