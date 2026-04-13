import json
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from agent.planner import plan
from agent.executor import run_stream
from agent.context import ContextWindow
from services.rag import close as close_weaviate
from profile import UserProfile, load_profile, save_profile

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)

_context = ContextWindow()


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await close_weaviate()


_default_origins = "http://localhost:5173,http://localhost:5174"
_allowed_origins = os.getenv("ALLOWED_ORIGINS", _default_origins).split(",")

app = FastAPI(title="Jobzoeker Chat", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class PlanRequest(BaseModel):
    message: str
    model: str = "gpt-4o-mini"

class RunRequest(BaseModel):
    plan: dict
    model: str = "gpt-4o-mini"


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------

@app.get("/profile", response_model=UserProfile)
async def get_profile():
    return load_profile()


@app.put("/profile", response_model=UserProfile)
async def update_profile(profile: UserProfile):
    save_profile(profile)
    return profile


# ---------------------------------------------------------------------------
# Chat — two-phase: plan then confirm+run
# ---------------------------------------------------------------------------

@app.post("/chat/plan")
async def chat_plan(req: PlanRequest):
    """Phase 1 — generate and return the plan. Nothing executes yet."""
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="message cannot be empty")

    _context.add_user(req.message)

    try:
        plan_dict = await plan(query=req.message, context=_context, model=req.model)
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))

    return plan_dict


@app.post("/chat/run")
async def chat_run(req: RunRequest):
    """
    Phase 2 — execute a confirmed plan, streaming task status via SSE.

    Event types:
      task_start  {"type": "task_start", "task_id": int}
      task_done   {"type": "task_done",  "task_id": int, "summary": str}
      complete    {"type": "complete"}
    """
    async def event_stream():
        async for event in run_stream(req.plan, _context, req.model):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/context")
async def get_context():
    """Return the current conversation context window."""
    return {"messages": _context.get_messages()}


@app.delete("/context")
async def reset_context():
    _context.clear()
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Frontend — serve built React app (production only)
# ---------------------------------------------------------------------------

_static_dir = Path(__file__).parent / "static"
if _static_dir.exists():
    app.mount("/assets", StaticFiles(directory=str(_static_dir / "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """Catch-all: serve index.html for any unknown route (SPA client-side routing)."""
        index = _static_dir / "index.html"
        # Serve known root-level static files (favicon, icons, etc.) directly
        candidate = _static_dir / full_path
        if candidate.is_file():
            return FileResponse(str(candidate))
        return FileResponse(str(index))
