"""E2E tests for the health check endpoint."""

import pytest


@pytest.mark.asyncio
async def test_health_returns_200(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] in ("healthy", "degraded", "starting")
    assert "database" in data
    assert data["version"] == "1.0.0"


@pytest.mark.asyncio
async def test_health_db_connected(client):
    import app.startup_state as startup_state

    startup_state.startup_complete = True
    resp = await client.get("/health")
    data = resp.json()
    assert data["database"] == "connected"
    assert data["status"] == "healthy"


@pytest.mark.asyncio
async def test_health_reports_starting_when_startup_incomplete(client):
    import app.startup_state as startup_state

    startup_state.startup_complete = False
    resp = await client.get("/health")
    data = resp.json()
    assert data["status"] == "starting"
    assert data["database"] == "initializing"
