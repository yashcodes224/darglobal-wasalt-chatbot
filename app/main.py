"""FastAPI app: serves the chat UI and POST /api/chat."""

import os
import time

from collections import defaultdict, deque
from contextlib import asynccontextmanager
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import llm
from .chatcore import answer
from .rag import load_index


STATIC = Path(__file__).parent / "static"
state = {}


@asynccontextmanager
async def lifespan(app):
    state["index"] = load_index(
        os.environ.get(
            "CHUNKS_PATH",
            "data/processed/chunks.jsonl"
        )
    )
    yield


app = FastAPI(
    title="DarGlobal & Wasalt Assistant",
    lifespan=lifespan
)

app.mount(
    "/static",
    StaticFiles(directory=STATIC),
    name="static"
)


class Turn(BaseModel):
    role: str
    content: str = Field(max_length=2000)


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=1000)
    history: Optional[List[Turn]] = None


_hits = defaultdict(deque)

RATE_PER_MIN = int(
    os.environ.get("RATE_LIMIT_PER_MIN", "12")
)


def rate_limited(ip):
    now = time.time()
    q = _hits[ip]

    while q and now - q[0] > 60:
        q.popleft()

    if len(q) >= RATE_PER_MIN:
        return True

    q.append(now)
    return False


@app.get("/health")
def health():
    idx = state.get("index")

    return {
        "status": "ok",
        "chunks": len(idx.chunks) if idx else 0,
        "llm_configured": bool(
            os.environ.get("OPENROUTER_API_KEY")
        ),
        "models": llm.models()
    }


@app.post("/api/chat")
async def chat(body: ChatIn, request: Request):
    client_ip = (
        request.client.host
        if request.client
        else "?"
    )

    ip = (
        request.headers.get("x-forwarded-for")
        or client_ip
    ).split(",")[0].strip()

    if rate_limited(ip):
        return JSONResponse(
            {
                "detail": (
                    "Too many requests. Please wait "
                    "a minute and try again."
                )
            },
            status_code=429
        )

    history = [
        {
            "role": t.role,
            "content": t.content
        }
        for t in (body.history or [])
    ]

    return await answer(
        state["index"],
        body.message,
        history
    )


@app.get("/")
def index():
    return FileResponse(
        STATIC / "index.html"
    )