"""
Health check endpoint.
GET /health — returns service status and DB connectivity.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter
from sqlalchemy import text

from app.schemas.task_schemas import HealthResponse
import app.startup_state as startup_state

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse, summary="Service health check")
async def health_check() -> HealthResponse:
    """
    Returns the operational status of the service and the database connection.
    """
    from app.db.database import async_session_factory

    if not startup_state.startup_complete:
        return HealthResponse(status="starting", database="initializing", version="1.0.0")

    if startup_state.startup_error:
        return HealthResponse(
            status="degraded",
            database=f"startup_error: {startup_state.startup_error}",
            version="1.0.0",
        )

    db_status = "unreachable"
    try:
        async with async_session_factory() as session:
            await session.execute(text("SELECT 1"))
            db_status = "connected"
    except Exception as e:
        logger.warning(f"[health] DB check failed: {e}")
        db_status = f"error: {type(e).__name__}"

    return HealthResponse(
        status="healthy" if db_status == "connected" else "degraded",
        database=db_status,
        version="1.0.0",
    )
