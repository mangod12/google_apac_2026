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
import asyncio

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes_health import router as health_router
from app.api.routes_tasks import demo_router, router as tasks_router
from app.config import settings
from app.mcp_server import mcp as mcp_server
import app.startup_state as startup_state

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
    allow_origins=settings.cors_origins_list,
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


# ── Startup / Shutdown ───────────────────────────────────

async def _init_db() -> None:
    """Create DB tables and pgvector extension — must finish before serving."""
    from app.db.database import engine
    from app.db.models import Base
    from sqlalchemy import text as sa_text

    async with engine.begin() as conn:
        await conn.execute(sa_text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
        try:
            await conn.execute(sa_text(
                "ALTER TABLE memory_entries ADD COLUMN IF NOT EXISTS embedding vector(3072)"
            ))
        except Exception:
            pass
        # Ensure FK matches model's ondelete="SET NULL" (create_all won't update existing constraints)
        try:
            await conn.execute(sa_text("""
                DO $$
                BEGIN
                    IF EXISTS (
                        SELECT 1 FROM pg_constraint
                        WHERE conname = 'memory_entries_task_id_fkey' AND confdeltype != 's'
                    ) THEN
                        ALTER TABLE memory_entries DROP CONSTRAINT memory_entries_task_id_fkey;
                        ALTER TABLE memory_entries ADD CONSTRAINT memory_entries_task_id_fkey
                            FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE SET NULL;
                    END IF;
                END $$;
            """))
        except Exception:
            pass
    logger.info("Database tables verified/created (pgvector enabled).")


async def _deferred_startup() -> None:
    """DB init + seed + warmup — runs AFTER uvicorn is already accepting connections."""
    # DB init (Cloud SQL proxy can take 10-30s on cold start)
    await _init_db()

    # Seed knowledge base
    try:
        from app.db.seed import seed_knowledge_base
        seeded = await seed_knowledge_base()
        if seeded:
            logger.info(f"Knowledge base seeded with {seeded} entries.")
    except Exception as e:
        logger.warning(f"Knowledge base seeding failed (non-fatal): {e}")

    # Presets are hardcoded in preset_data.py — no warmup needed
    from app.api.routes_tasks import _response_cache, PRESET_QUERIES
    cached = len([q for q in PRESET_QUERIES if q in _response_cache])
    logger.info(f"Presets ready: {cached}/{len(PRESET_QUERIES)} loaded from hardcoded data.")


@app.on_event("startup")
async def on_startup() -> None:
    logger.info("TaskForge starting up...")

    # Register all tools (pure Python imports — instant, no I/O)
    import app.tools.task_tools       # noqa: F401
    import app.tools.knowledge_tool   # noqa: F401
    import app.tools.calendar_tool    # noqa: F401
    import app.tools.weather_tool     # noqa: F401
    import app.tools.route_tool      # noqa: F401
    import app.tools.disaster_feed   # noqa: F401
    logger.info("Tools registered.")

    logger.info(
        f"TaskForge ready | model={settings.gemini_model} | "
        f"vertex_ai={settings.use_vertex_ai}"
    )

    # ALL I/O (DB + seed + warmup) runs after port binds
    async def _run_startup_work() -> None:
        try:
            await _deferred_startup()
            startup_state.startup_error = None
        except Exception as exc:
            startup_state.startup_error = str(exc)
            logger.exception("Deferred startup failed")
        finally:
            startup_state.startup_complete = True

    asyncio.create_task(_run_startup_work())


@app.on_event("shutdown")
async def on_shutdown() -> None:
    logger.info("TaskForge shutting down...")
    from app.db.database import engine
    await engine.dispose()


# ── Routers ──────────────────────────────────────────────

app.include_router(health_router)
app.include_router(tasks_router)
app.include_router(demo_router)


# ── MCP Server (Model Context Protocol) ─────────────────

from mcp.server.sse import SseServerTransport
from starlette.requests import Request

_sse_transport = SseServerTransport("/mcp/messages/")


@app.get("/mcp/sse")
async def mcp_sse_endpoint(request: Request):
    """SSE endpoint for MCP client connections."""
    async with _sse_transport.connect_sse(
        request.scope, request.receive, request._send
    ) as (read_stream, write_stream):
        await mcp_server._mcp_server.run(
            read_stream, write_stream,
            mcp_server._mcp_server.create_initialization_options(),
        )


from starlette.routing import Mount as _Mount  # noqa: E402
app.router.routes.append(
    _Mount("/mcp/messages/", app=_sse_transport.handle_post_message)
)
logger.info("MCP server mounted at /mcp/sse (SSE transport)")


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
