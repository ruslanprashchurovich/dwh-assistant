import os
import io
from pathlib import Path
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from .services.database import execute_sql_query, build_dbml_schema
from .services.llm import natural_language_to_sql, get_default_provider_name, PROVIDERS
from .services.memory import session_manager

assistant_app = FastAPI(title="DWH Assistant")

# Configure static files and templates
BASE_DIR = Path(__file__).resolve().parent
assistant_app.mount(
    "/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static"
)
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

debug_mode = os.getenv("DEBUG_MODE", "0") == "1"

SESSION_COOKIE = "dwh_session_id"


def get_session_id(request: Request) -> str:
    """Get session ID from cookie, or return empty string if none."""
    return request.cookies.get(SESSION_COOKIE, "")


def ensure_session(request: Request, response: Response) -> str:
    """Get existing session ID or create a new one and set cookie."""
    session_id = get_session_id(request)
    if not session_id or not session_manager.session_exists(session_id):
        session_id = session_manager.generate_session_id()
        response.set_cookie(
            key=SESSION_COOKIE,
            value=session_id,
            httponly=True,
            samesite="lax",
            max_age=86400,  # 24 hours
        )
    return session_id


@assistant_app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    response = templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "default_provider": get_default_provider_name(),
            "providers": list(PROVIDERS.keys()),
        },
    )
    # Ensure session cookie is set on first visit
    ensure_session(request, response)
    return response


@assistant_app.post("/")
async def handle_post(request: Request):
    content_type = request.headers.get("content-type", "")
    x_requested_with = request.headers.get("x-requested-with", "")

    # AJAX JSON request (Manual SQL)
    if x_requested_with == "XMLHttpRequest" and "application/json" in content_type:
        return await handle_ajax_request(request)

    # Form request (Natural Language)
    return await handle_form_request(request)


@assistant_app.post("/clear-memory")
async def clear_memory(request: Request):
    """Clear the conversation memory for the current session."""
    session_id = get_session_id(request)
    if session_id:
        session_manager.clear_session(session_id)
    return JSONResponse({"status": "ok", "message": "Conversation memory cleared"})


@assistant_app.get("/memory-status")
async def memory_status(request: Request):
    """Return current memory info for the session (for debugging)."""
    session_id = get_session_id(request)
    if not session_id:
        return JSONResponse({"session_id": None, "exists": False, "size": 0})
    return JSONResponse(session_manager.get_session_info(session_id))


async def handle_ajax_request(request: Request):
    data = await request.json()
    manual_query = data.get("manualQuery")
    if manual_query:
        print("*", manual_query)
        return await process_query(manual_query)
    return JSONResponse({"error": "No manual query provided"}, status_code=400)


async def handle_form_request(request: Request):
    form = await request.form()
    user_query = form.get("user_query")
    model = form.get("model", get_default_provider_name())
    if user_query:
        response = await process_natural_language_query(user_query, model, request)
        # Ensure session cookie is present on response
        session_id = get_session_id(request)
        if not session_id:
            session_id = session_manager.generate_session_id()
            response.set_cookie(
                key=SESSION_COOKIE,
                value=session_id,
                httponly=True,
                samesite="lax",
                max_age=86400,
            )
        return response
    return JSONResponse({"error": "No user query provided"}, status_code=400)


@assistant_app.post("/download-csv")
async def download_csv(request: Request):
    """Execute SQL and return full result as CSV."""
    data = await request.json()
    sql = data.get("sql", "").strip()
    if not sql:
        return JSONResponse({"error": "No SQL provided"}, status_code=400)
    try:
        ch_answer = await execute_sql_query(sql)
        if ch_answer["error"]:
            return JSONResponse({"error": str(ch_answer["error"])})
        csv_data = ch_answer["result"].to_csv(index=False)
        # Add UTF-8 BOM for Excel compatibility
        output = io.BytesIO()
        output.write(b"\xef\xbb\xbf")
        output.write(csv_data.encode("utf-8"))
        output.seek(0)
        return StreamingResponse(
            output,
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": "attachment; filename=full_dataset.csv"},
        )
    except Exception as e:
        return JSONResponse({"error": str(e)})


async def process_query(query: str):
    try:
        ch_answer = await execute_sql_query(query)
        if ch_answer["error"]:
            return JSONResponse({"error": str(ch_answer["error"])})
        df = ch_answer["result"]
        return JSONResponse(
            {
                "result": df.to_html(classes="table table-striped", index=False),
                "sql": query,
                "totalRows": len(df),
                "totalCols": len(df.columns),
            }
        )
    except Exception as e:
        return JSONResponse(
            {"error": f"Произошла ошибка при выполнении запроса: {str(e)}"}
        )


async def process_natural_language_query(
    user_query: str, provider_name: str, request: Request
):
    # Get or create session memory
    session_id = get_session_id(request)
    if not session_id:
        session_id = session_manager.generate_session_id()
    memory = session_manager.get_or_create(session_id)

    # Add user message to memory
    memory.add_user_message(user_query)

    # Get conversation history (excluding current query — it's passed separately)
    history = memory.get_history()[:-1]

    dbml_schema = await build_dbml_schema()
    llm_answer = await natural_language_to_sql(
        user_query=user_query,
        schema_data=dbml_schema,
        provider_name=provider_name,
        conversation_history=history if history else None,
        debug_mode=debug_mode,
    )

    if llm_answer["status"] == "success":
        # Add assistant response (the SQL) to memory
        memory.add_assistant_message(llm_answer["sql"])
        return await process_query(llm_answer["sql"])

    # Add error response to memory so LLM knows what failed
    error_msg = llm_answer.get("error_description", "Unknown error")
    memory.add_assistant_message(f"Error: {error_msg}")

    return JSONResponse(
        {
            "error": llm_answer["error_description"],
            "sql": llm_answer.get("sql", ""),
            "rawResponse": llm_answer.get("raw_response", "Нет сырого ответа"),
        }
    )
