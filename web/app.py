"""FastAPI web application — token display page and SSE endpoint."""

import asyncio
import json
import logging
import os
from typing import AsyncIterator, Optional
from urllib.parse import parse_qs

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

from db.database import (
    get_full_status,
    get_counters,
    get_counter,
    create_token,
    get_token,
    tokens_ahead,
    get_current_token_for_counter,
    verify_staff,
    get_staff_by_id,
    call_next_token,
    call_previous_token,
    recall_current_token,
    set_counter_status,
    get_waiting_tokens,
)

logger = logging.getLogger(__name__)

app = FastAPI(title="Queue Management")
SECRET_KEY = os.getenv("SECRET_KEY", "change-this-to-a-random-secret")
SESSION_COOKIE_NAME = "staff_session"
SESSION_MAX_AGE = 60 * 60 * 24 * 7
serializer = URLSafeTimedSerializer(SECRET_KEY, salt="staff-session")

# Mount static files
_static_dir = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=_static_dir), name="static")

# ---------------------------------------------------------------------------
# Pre-load static HTML files at startup
# ---------------------------------------------------------------------------
_html_cache: dict[str, str] = {}


@app.on_event("startup")
async def _preload_html() -> None:
    from db.database import init_db
    await init_db()
    for name in ("index.html", "take.html", "track.html", "staff_login.html", "staff_dashboard.html"):
        path = os.path.join(_static_dir, name)
        with open(path, encoding="utf-8") as f:
            _html_cache[name] = f.read()


def _parse_assigned_counters(raw_value: str) -> set[int]:
    if not raw_value:
        return set()
    result = set()
    for part in raw_value.split(","):
        part = part.strip()
        if part.isdigit():
            result.add(int(part))
    return result


async def get_current_staff(request: Request) -> Optional[dict]:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        return None
    try:
        payload = serializer.loads(token, max_age=SESSION_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return None
    staff_id = payload.get("staff_id")
    if not isinstance(staff_id, int):
        return None
    staff = await get_staff_by_id(staff_id)
    if not staff or int(staff.get("is_active") or 0) != 1:
        return None
    return staff


async def _require_staff(request: Request):
    staff = await get_current_staff(request)
    if not staff:
        return RedirectResponse(url="/staff/login", status_code=302), None
    return None, staff


def _can_operate_counter(staff: dict, counter_id: int) -> bool:
    assigned = _parse_assigned_counters(staff.get("assigned_counters") or "")
    if not assigned:
        return True
    return counter_id in assigned


# ---------------------------------------------------------------------------
# SSE broadcast helpers
# ---------------------------------------------------------------------------

_sse_queues: list[asyncio.Queue] = []


async def broadcast_update() -> None:
    """Push a status update to all connected SSE clients."""
    try:
        status = await get_full_status()
        payload = json.dumps(status)
        dead = []
        for q in _sse_queues:
            try:
                q.put_nowait(payload)
            except asyncio.QueueFull:
                dead.append(q)
        for q in dead:
            _sse_queues.remove(q)
    except Exception:
        logger.exception("broadcast_update failed")


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def index():
    return HTMLResponse(content=_html_cache.get("index.html", ""))


@app.get("/take", response_class=HTMLResponse)
async def take_page():
    return HTMLResponse(content=_html_cache.get("take.html", ""))


@app.get("/track/{token_id}", response_class=HTMLResponse)
async def track_page(token_id: int):
    safe_id = json.dumps(int(token_id))
    content = _html_cache.get("track.html", "").replace("{{TOKEN_ID}}", safe_id)
    return HTMLResponse(content=content)


@app.get("/api/counters")
async def api_counters():
    """Return ALL counters with their status so the take page can show open vs closed."""
    counters = await get_counters(include_closed=True)
    return JSONResponse([
        {"id": c["id"], "name": c["name"], "status": c["status"]}
        for c in counters
    ])


@app.post("/api/token")
async def api_take_token(request: Request):
    data = await request.json()
    name = data.get("name", "").strip()
    counter_id = data.get("counter_id")
    purpose = data.get("purpose", "").strip() or None

    if not name or not counter_id:
        return JSONResponse({"error": "name and counter_id are required"}, status_code=400)

    # Verify counter is open
    from db.database import get_counter
    counter = await get_counter(int(counter_id))
    if not counter:
        return JSONResponse({"error": "Counter not found"}, status_code=404)
    if counter["status"] != "open":
        return JSONResponse({"error": "This counter is currently closed"}, status_code=400)

    token = await create_token(
        counter_id=int(counter_id),
        customer_name=name,
        purpose=purpose,
    )
    await broadcast_update()
    return JSONResponse({"token_id": token["id"], "token_number": token["token_number"]})


@app.get("/api/track/{token_id}")
async def api_track(token_id: int):
    token = await get_token(token_id)
    if not token:
        return JSONResponse({"error": "Token not found"}, status_code=404)
    ahead = await tokens_ahead(token_id)
    current = await get_current_token_for_counter(token["counter_id"])
    return JSONResponse(
        {
            "token_id": token_id,
            "token_number": token["token_number"],
            "status": token["status"],
            "ahead": ahead,
            "current_serving": current["token_number"] if current else None,
        }
    )


@app.get("/events")
async def sse_events(request: Request):
    """Server-Sent Events endpoint for live display updates."""

    async def event_stream() -> AsyncIterator[str]:
        q: asyncio.Queue = asyncio.Queue(maxsize=10)
        _sse_queues.append(q)
        try:
            # Send initial state
            status = await get_full_status()
            yield f"data: {json.dumps(status)}\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    payload = await asyncio.wait_for(q.get(), timeout=20)
                    yield f"data: {payload}\n\n"
                except asyncio.TimeoutError:
                    yield ": ping\n\n"
        finally:
            if q in _sse_queues:
                _sse_queues.remove(q)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/staff/login", response_class=HTMLResponse)
async def staff_login_page():
    return HTMLResponse(content=_html_cache.get("staff_login.html", ""))


@app.post("/staff/login")
async def staff_login(request: Request):
    form = parse_qs((await request.body()).decode("utf-8"))
    username = (form.get("username", [""])[0] or "").strip()
    password = form.get("password", [""])[0] or ""
    staff = await verify_staff(username, password)
    if not staff:
        return RedirectResponse(url="/staff/login?error=1", status_code=302)
    payload = {"staff_id": staff["id"], "username": staff["username"]}
    signed = serializer.dumps(payload)
    response = RedirectResponse(url="/staff", status_code=302)
    response.set_cookie(
        SESSION_COOKIE_NAME,
        signed,
        max_age=SESSION_MAX_AGE,
        httponly=True,
        samesite="lax",
    )
    return response


@app.get("/staff/logout")
async def staff_logout():
    response = RedirectResponse(url="/staff/login", status_code=302)
    response.delete_cookie(SESSION_COOKIE_NAME)
    return response


@app.get("/staff", response_class=HTMLResponse)
async def staff_dashboard(request: Request):
    redirect, staff = await _require_staff(request)
    if redirect:
        return redirect
    username = json.dumps(staff.get("display_name") or staff["username"])
    content = _html_cache.get("staff_dashboard.html", "").replace("{{USERNAME}}", username)
    return HTMLResponse(content=content)


@app.get("/api/staff/counters")
async def api_staff_counters(request: Request):
    redirect, staff = await _require_staff(request)
    if redirect:
        return redirect
    counters = await get_counters(include_closed=True)
    assigned = _parse_assigned_counters(staff.get("assigned_counters") or "")
    if assigned:
        counters = [c for c in counters if c["id"] in assigned]
    result = []
    for c in counters:
        waiting = await get_waiting_tokens(c["id"])
        current = await get_current_token_for_counter(c["id"])
        result.append(
            {
                "id": c["id"],
                "name": c["name"],
                "status": c["status"],
                "current_token": current["token_number"] if current else None,
                "waiting_count": len(waiting),
            }
        )
    return JSONResponse(result)


@app.get("/api/staff/status")
async def api_staff_status(request: Request):
    redirect, _staff = await _require_staff(request)
    if redirect:
        return redirect
    return JSONResponse(await get_full_status())


@app.post("/api/staff/token/next")
async def api_staff_token_next(request: Request):
    redirect, staff = await _require_staff(request)
    if redirect:
        return redirect
    data = await request.json()
    counter_id = int(data.get("counter_id") or 0)
    if counter_id <= 0 or not _can_operate_counter(staff, counter_id):
        return JSONResponse({"error": "Counter not allowed"}, status_code=403)
    token = await call_next_token(counter_id)
    await broadcast_update()
    return JSONResponse({"ok": True, "token": token})


@app.post("/api/staff/token/recall")
async def api_staff_token_recall(request: Request):
    redirect, staff = await _require_staff(request)
    if redirect:
        return redirect
    data = await request.json()
    counter_id = int(data.get("counter_id") or 0)
    if counter_id <= 0 or not _can_operate_counter(staff, counter_id):
        return JSONResponse({"error": "Counter not allowed"}, status_code=403)
    token = await recall_current_token(counter_id)
    await broadcast_update()
    return JSONResponse({"ok": True, "token": token})


@app.post("/api/staff/token/prev")
async def api_staff_token_prev(request: Request):
    redirect, staff = await _require_staff(request)
    if redirect:
        return redirect
    data = await request.json()
    counter_id = int(data.get("counter_id") or 0)
    if counter_id <= 0 or not _can_operate_counter(staff, counter_id):
        return JSONResponse({"error": "Counter not allowed"}, status_code=403)
    token = await call_previous_token(counter_id)
    await broadcast_update()
    return JSONResponse({"ok": True, "token": token})


@app.post("/api/staff/counter/toggle")
async def api_staff_counter_toggle(request: Request):
    redirect, staff = await _require_staff(request)
    if redirect:
        return redirect
    data = await request.json()
    counter_id = int(data.get("counter_id") or 0)
    if counter_id <= 0 or not _can_operate_counter(staff, counter_id):
        return JSONResponse({"error": "Counter not allowed"}, status_code=403)
    counter = await get_counter(counter_id)
    if not counter:
        return JSONResponse({"error": "Counter not found"}, status_code=404)
    next_status = "closed" if counter["status"] == "open" else "open"
    await set_counter_status(counter_id, next_status)
    await broadcast_update()
    return JSONResponse({"ok": True, "status": next_status})
