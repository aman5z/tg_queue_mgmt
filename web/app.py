"""FastAPI web application — token display page and SSE endpoint."""

import asyncio
import json
import os
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from db.database import (
    get_full_status,
    get_counters,
    create_token,
    get_token,
    tokens_ahead,
    get_current_token_for_counter,
)

app = FastAPI(title="Queue Management")

# Mount static files
_static_dir = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=_static_dir), name="static")

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
        pass


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def index():
    path = os.path.join(_static_dir, "index.html")
    with open(path) as f:
        return HTMLResponse(content=f.read())


@app.get("/take", response_class=HTMLResponse)
async def take_page():
    path = os.path.join(_static_dir, "take.html")
    with open(path) as f:
        return HTMLResponse(content=f.read())


@app.get("/track/{token_id}", response_class=HTMLResponse)
async def track_page(token_id: int):
    path = os.path.join(_static_dir, "track.html")
    with open(path) as f:
        content = f.read().replace("{{TOKEN_ID}}", str(token_id))
        return HTMLResponse(content=content)


@app.get("/api/counters")
async def api_counters():
    counters = await get_counters(include_closed=False)
    return JSONResponse([{"id": c["id"], "name": c["name"]} for c in counters])


@app.post("/api/token")
async def api_take_token(request: Request):
    data = await request.json()
    name = data.get("name", "").strip()
    counter_id = data.get("counter_id")
    purpose = data.get("purpose", "").strip() or None

    if not name or not counter_id:
        return JSONResponse({"error": "name and counter_id are required"}, status_code=400)

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
                    # Keepalive ping
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
