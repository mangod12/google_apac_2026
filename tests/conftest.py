"""
Test configuration — fixtures for E2E testing against real PostgreSQL.

All tests share a single event loop (session scope) to avoid asyncpg
"attached to a different loop" errors with the module-level engine.
"""

from __future__ import annotations

import pytest_asyncio
import httpx
from sqlalchemy import text

from app.main import app
from app.db.database import engine, async_session_factory
from app.db.models import Base


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_database():
    """Create all tables once at session start. Tables are NOT dropped so the
    running dev server keeps working after tests finish."""
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
    yield


@pytest_asyncio.fixture(autouse=True)
async def clean_tables():
    """Truncate all tables after each test for isolation."""
    yield
    async with async_session_factory() as session:
        await session.execute(text("TRUNCATE tasks, agent_logs, memory_entries CASCADE"))
        await session.commit()


@pytest_asyncio.fixture
async def client():
    """Async HTTP client bound to the FastAPI app."""
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as ac:
        yield ac
