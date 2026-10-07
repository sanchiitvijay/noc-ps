"""
Development route and SQL query logger middleware.

Captures for every incoming HTTP request:
  - Route triggered (HTTP method, path, full URL, query parameters, client IP, headers)
  - Full request body (without truncation)
  - All SQL queries executed during the route handling:
      - SQL statement
      - Query parameters
      - Query execution duration
      - Full result data (all fetched rows or affected row counts, without truncation)
  - Total roundtrip latency from route trigger to returning response
  - Full response status code, response headers, and response body (without truncation)
  - Full exception traceback if an error occurs

Appends all entries to the single file `log.txt`.
"""

from __future__ import annotations

import asyncio
import contextvars
from datetime import date, datetime, time
import json
import logging
from pathlib import Path
import time as time_module
import traceback
from typing import Any, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)

# Context variable that stores the list of SQL queries executed for the current request
_current_request_queries: contextvars.ContextVar[list[dict] | None] = contextvars.ContextVar(
    "_current_request_queries", default=None
)

# Async lock to ensure synchronized appending to the log file
_write_lock = asyncio.Lock()


def record_sql_query(record: dict) -> None:
    """Record an executed SQL query and its details into the current request context."""
    queries = _current_request_queries.get()
    if queries is not None:
        queries.append(record)


def get_current_request_queries() -> list[dict] | None:
    """Return the list of SQL queries collected for the current request context."""
    return _current_request_queries.get()


def clear_current_request_queries() -> None:
    """Clear any collected SQL queries in the current request context."""
    queries = _current_request_queries.get()
    if queries is not None:
        queries.clear()


def get_dev_log_path() -> Path:
    """Resolve the path to the dev log.txt file.

    Ensures that log.txt is accessible in both backend/ and the project root.
    """
    from config import settings

    raw_path = getattr(settings, "DEV_LOG_FILE", "log.txt")
    p = Path(raw_path)
    if p.is_absolute():
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    # backend/ directory
    backend_dir = Path(__file__).resolve().parent.parent
    log_file = backend_dir / p.name
    log_file.parent.mkdir(parents=True, exist_ok=True)

    # Create / maintain symlink in workspace root if different from backend
    root_dir = backend_dir.parent
    root_file = root_dir / p.name
    if root_dir != backend_dir:
        try:
            if not root_file.exists() and not root_file.is_symlink():
                root_file.symlink_to(Path("backend") / p.name)
            elif root_file.is_symlink() and not root_file.exists():
                # Re-create broken symlink
                root_file.unlink(missing_ok=True)
                root_file.symlink_to(Path("backend") / p.name)
        except Exception:
            pass

    return log_file


async def append_to_dev_log(content: str) -> None:
    """Thread-safe and async-safe append to the dev log.txt file."""
    async with _write_lock:
        def _write():
            path = get_dev_log_path()
            with open(path, "a", encoding="utf-8") as f:
                f.write(content)
                f.flush()

        await asyncio.to_thread(_write)


def _safe_json_serialize(obj: Any) -> Any:
    """Recursively convert objects to JSON-serializable primitives without truncation."""
    if obj is None or isinstance(obj, (int, float, bool, str)):
        return obj
    if isinstance(obj, (datetime, date, time)):
        return obj.isoformat()
    if isinstance(obj, bytes):
        try:
            return obj.decode("utf-8")
        except Exception:
            return f"<binary data: {len(obj)} bytes>"
    if isinstance(obj, (list, tuple, set)):
        return [_safe_json_serialize(item) for item in obj]
    if isinstance(obj, dict):
        return {str(k): _safe_json_serialize(v) for k, v in obj.items()}
    if hasattr(obj, "keys") and callable(getattr(obj, "keys", None)):
        try:
            return {str(k): _safe_json_serialize(obj[k]) for k in obj.keys()}
        except Exception:
            pass
    return str(obj)


def _format_body(body_bytes: bytes, content_type: str = "") -> str:
    """Format request or response body for human readability without any truncation."""
    if not body_bytes:
        return "(empty)"

    content_type_lower = content_type.lower()

    # Try parsing as JSON first
    try:
        parsed = json.loads(body_bytes.decode("utf-8"))
        return json.dumps(_safe_json_serialize(parsed), indent=2, ensure_ascii=False)
    except Exception:
        pass

    # Try decoding as text
    try:
        text = body_bytes.decode("utf-8")
        return text
    except UnicodeDecodeError:
        return f"[Binary Content: {len(body_bytes)} bytes, Content-Type: {content_type}]"


def _format_sql_query(idx: int, q: dict) -> str:
    """Format a single SQL query execution record cleanly without truncation."""
    lines = []
    duration_ms = q.get("duration_ms", 0.0)
    lines.append("----------------------------------------")
    lines.append(f"[SQL Query #{idx}] (Execution Time: {duration_ms:.2f} ms)")
    lines.append("----------------------------------------")

    ts = q.get("timestamp")
    if isinstance(ts, datetime):
        lines.append(f"Timestamp:   {ts.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}")

    query_str = q.get("query", "").strip()
    lines.append("SQL:")
    for qline in query_str.splitlines():
        lines.append(f"  {qline}")

    params = q.get("params")
    if params is None or params == () or params == []:
        lines.append("Parameters:  None")
    else:
        try:
            serialized_params = _safe_json_serialize(params)
            if (
                isinstance(params, (tuple, list))
                and len(params) <= 5
                and not any(isinstance(x, (dict, list)) for x in params)
            ):
                lines.append(f"Parameters:  {tuple(serialized_params)!r}")
            else:
                lines.append("Parameters:")
                params_json = json.dumps(serialized_params, indent=2, ensure_ascii=False)
                for pline in params_json.splitlines():
                    lines.append(f"  {pline}")
        except Exception:
            lines.append(f"Parameters:  {params!r}")

    if "batch_count" in q:
        lines.append(f"Batch Count: {q['batch_count']} parameter sets")

    if q.get("error"):
        lines.append(f"Query Error: {q['error']}")
    else:
        lines.append("Result:")
        is_select = q.get("is_select", False)
        fetched = q.get("fetched", False)
        rows = q.get("rows", [])

        if is_select or fetched or len(rows) > 0:
            lines.append(f"  Rows Fetched: {len(rows)}")
            if len(rows) == 0:
                lines.append("  Data: []")
            else:
                lines.append("  Data:")
                try:
                    data_json = json.dumps(_safe_json_serialize(rows), indent=2, ensure_ascii=False)
                    for dline in data_json.splitlines():
                        lines.append(f"    {dline}")
                except Exception:
                    lines.append(f"    {rows!r}")
        else:
            rowcount = q.get("rowcount")
            lastrowid = q.get("lastrowid")
            if rowcount is not None and rowcount >= 0:
                lines.append(f"  Rows Affected:  {rowcount}")
            if lastrowid is not None:
                lines.append(f"  Last Insert ID: {lastrowid}")
            if (rowcount is None or rowcount < 0) and lastrowid is None:
                lines.append("  Statement executed successfully (no rows returned/affected)")

    return "\n".join(lines)


def _format_dev_log_entry(
    request: Request,
    body_bytes: bytes,
    response: Response | None,
    response_body_bytes: bytes,
    queries: list[dict],
    duration_ms: float,
    start_time_dt: datetime,
    error: Exception | None = None,
) -> str:
    """Format the complete route log entry for log.txt."""
    sep_major = "=" * 100
    sep_section = "-" * 100

    method = request.method
    url_path = request.url.path
    full_url = str(request.url)
    client_ip = (
        request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
        or (request.client.host if request.client else "unknown")
    )

    status_code = response.status_code if response else 500
    try:
        from http import HTTPStatus
        status_phrase = HTTPStatus(status_code).phrase
    except Exception:
        status_phrase = ""

    duration_s = duration_ms / 1000.0
    timestamp_str = start_time_dt.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

    lines = [
        sep_major,
        f"[{timestamp_str}] ROUTE TRIGGERED: {method} {url_path}",
        sep_major,
        f"Route Triggered:  {method} {url_path}",
        f"Full URL:         {full_url}",
        f"Client IP:        {client_ip}",
        f"Status Code:      {status_code} {status_phrase}".strip(),
        f"Total Time Taken: {duration_ms:.2f} ms ({duration_s:.4f} seconds)",
        f"Timestamp:        {timestamp_str}",
        "",
        sep_section,
        "[REQUEST DETAILS]",
        sep_section,
        f"HTTP Method:      {method}",
        f"URL Path:         {url_path}",
    ]

    # Query parameters
    query_params = dict(request.query_params)
    if query_params:
        lines.append("Query Parameters:")
        for k, v in query_params.items():
            lines.append(f"  {k}: {v}")
    else:
        lines.append("Query Parameters: None")

    # Request headers
    lines.append("")
    lines.append("Request Headers:")
    for hk, hv in request.headers.items():
        lines.append(f"  {hk}: {hv}")

    # Request body
    lines.append("")
    lines.append("Request Body:")
    req_body_str = _format_body(body_bytes, request.headers.get("content-type", ""))
    for bline in req_body_str.splitlines():
        lines.append(f"  {bline}")

    # SQL Queries
    lines.append("")
    lines.append(sep_section)
    lines.append(f"[SQL QUERIES EXECUTED ({len(queries)})]")
    lines.append(sep_section)
    if not queries:
        lines.append("No SQL queries were executed for this route.")
    else:
        total_sql_ms = sum(q.get("duration_ms", 0.0) for q in queries)
        lines.append(f"Total SQL Execution Time: {total_sql_ms:.2f} ms")
        lines.append("")
        for idx, q in enumerate(queries, 1):
            lines.append(_format_sql_query(idx, q))
            lines.append("")

    # Error if any
    if error is not None:
        lines.append(sep_section)
        lines.append("[EXCEPTION / ERROR]")
        lines.append(sep_section)
        lines.append(f"Exception Type:   {type(error).__name__}")
        lines.append(f"Exception Detail: {error}")
        lines.append("Traceback:")
        for tb_line in traceback.format_exc().splitlines():
            lines.append(f"  {tb_line}")
        lines.append("")

    # Response Details
    lines.append(sep_section)
    lines.append("[RESPONSE DETAILS]")
    lines.append(sep_section)
    lines.append(f"Status Code:      {status_code} {status_phrase}".strip())
    lines.append(f"Total Time Taken: {duration_ms:.2f} ms ({duration_s:.4f} seconds)")

    if response:
        lines.append("")
        lines.append("Response Headers:")
        for rhk, rhv in response.headers.items():
            lines.append(f"  {rhk}: {rhv}")

    lines.append("")
    lines.append("Response Body:")
    resp_content_type = response.headers.get("content-type", "") if response else ""
    resp_body_str = _format_body(response_body_bytes, resp_content_type)
    for rline in resp_body_str.splitlines():
        lines.append(f"  {rline}")

    lines.append("")
    lines.append(sep_major)
    lines.append("\n")

    return "\n".join(lines)


class DevLoggingMiddleware(BaseHTTPMiddleware):
    """Starlette middleware for development logging.

    Logs every incoming route, total roundtrip time, and all SQL queries and data
    to `log.txt` without truncation.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process the request, track all SQL queries, and log the result to log.txt."""
        start_time_perf = time_module.perf_counter()
        start_time_dt = datetime.now()

        # Initialize SQL query collector for this request
        queries: list[dict] = []
        token = _current_request_queries.set(queries)

        # Buffer request body so downstream handlers and this logger can read it
        body_bytes: bytes = b""
        try:
            body_bytes = await request.body()
        except Exception:
            pass

        async def _receive():
            return {"type": "http.request", "body": body_bytes, "more_body": False}

        request._receive = _receive  # type: ignore[attr-defined]

        response: Response | None = None
        error: Exception | None = None

        try:
            response = await call_next(request)
        except Exception as exc:
            error = exc
            raise
        finally:
            end_time_perf = time_module.perf_counter()
            duration_ms = (end_time_perf - start_time_perf) * 1000.0

            response_body_bytes = b""
            if response is not None:
                try:
                    chunks = []
                    async for chunk in response.body_iterator:
                        chunks.append(chunk)
                    response_body_bytes = b"".join(chunks)

                    async def _reiterate():
                        for c in chunks:
                            yield c

                    response.body_iterator = _reiterate()
                except Exception:
                    pass

            # Snapshot collected queries
            captured_queries = list(queries)

            # Format entry
            try:
                log_entry = _format_dev_log_entry(
                    request=request,
                    body_bytes=body_bytes,
                    response=response,
                    response_body_bytes=response_body_bytes,
                    queries=captured_queries,
                    duration_ms=duration_ms,
                    start_time_dt=start_time_dt,
                    error=error,
                )
                await append_to_dev_log(log_entry)
            except Exception as log_exc:
                logger.error("Failed to append to dev log.txt: %s", log_exc, exc_info=True)
            finally:
                _current_request_queries.reset(token)

        return response
