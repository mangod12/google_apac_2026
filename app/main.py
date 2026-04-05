"""
FastAPI application entry point for TaskForge.

Startup:
- Creates DB tables (if they don't exist) via SQLAlchemy
- Registers tool modules (triggers tool_registry.register calls)

Routes:
- /health          — Health check
- /api/v1/tasks    — Task CRUD + agent pipeline
- /docs            — Swagger UI (auto-generated)
- /redoc           — ReDoc UI (auto-generated)
"""

from __future__ import annotations

import logging
import logging.config

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes_health import router as health_router
from app.api.routes_tasks import demo_router, router as tasks_router
from app.config import settings

# ── Logging setup ────────────────────────────────────────

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ── FastAPI app ──────────────────────────────────────────

app = FastAPI(
    title="TaskForge — Multi-Agent Orchestration API",
    description=(
        "A production-grade multi-agent system where an Orchestrator coordinates "
        "Planner, Researcher, and Reviewer sub-agents to break down, research, plan, "
        "and validate complex tasks — powered by Gemini (Vertex AI) and PostgreSQL."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS ─────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Startup / Shutdown ───────────────────────────────────

@app.on_event("startup")
async def on_startup() -> None:
    logger.info("TaskForge starting up...")

    # Create DB tables
    from app.db.database import engine
    from app.db.models import Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables verified/created.")

    # Register all tools (imports trigger tool_registry.register calls)
    import app.tools.task_tools       # noqa: F401
    import app.tools.knowledge_tool   # noqa: F401
    import app.tools.calendar_tool    # noqa: F401
    import app.tools.weather_tool     # noqa: F401
    logger.info("Tools registered.")

    logger.info(
        f"TaskForge ready | model={settings.gemini_model} | "
        f"vertex_ai={settings.use_vertex_ai}"
    )


@app.on_event("shutdown")
async def on_shutdown() -> None:
    logger.info("TaskForge shutting down...")
    from app.db.database import engine
    await engine.dispose()


# ── Routers ──────────────────────────────────────────────

app.include_router(health_router)
app.include_router(tasks_router)
app.include_router(demo_router)


# ── Static files + Root ──────────────────────────────────

_static_dir = Path(__file__).parent / "static"
if _static_dir.is_dir():
    app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")


@app.get("/", include_in_schema=False, response_class=HTMLResponse)
async def root():
    index = _static_dir / "index.html"
    if index.exists():
        return HTMLResponse(content=index.read_text(encoding="utf-8"))
    return HTMLResponse(content="<h1>TaskForge API running</h1>")
