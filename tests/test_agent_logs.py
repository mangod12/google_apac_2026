"""E2E tests for agent logs endpoint."""

import os
import uuid

import pytest

# Skip LLM-dependent tests when no Gemini API key is configured
_requires_llm = pytest.mark.skipif(
    not os.environ.get("GEMINI_API_KEY") and not os.environ.get("VERTEX_AI_PROJECT"),
    reason="GEMINI_API_KEY or VERTEX_AI_PROJECT not set — skipping LLM-dependent tests",
)


@_requires_llm
@pytest.mark.asyncio
async def test_logs_after_execute(client):
    """Agent logs are created during pipeline execution."""
    exec_resp = await client.post("/execute", json={"query": "Flood in Odisha"})
    assert exec_resp.status_code == 200

    # Get the task that was created
    list_resp = await client.get("/api/v1/tasks")
    tasks = list_resp.json()["tasks"]
    assert len(tasks) >= 1
    task_id = tasks[0]["id"]

    # Fetch logs
    logs_resp = await client.get(f"/api/v1/tasks/{task_id}/logs")
    assert logs_resp.status_code == 200
    logs = logs_resp.json()

    assert len(logs) >= 2  # At least pipeline_start + pipeline_complete
    agent_names = {log["agent_name"] for log in logs}
    assert "orchestrator" in agent_names

    actions = {log["action"] for log in logs}
    assert "pipeline_start" in actions
    assert "pipeline_complete" in actions

    # Each log has required fields
    for log in logs:
        assert "id" in log
        assert "task_id" in log
        assert log["task_id"] == task_id
        assert "agent_name" in log
        assert "action" in log
        assert "created_at" in log


@pytest.mark.asyncio
async def test_logs_not_found_for_missing_task(client):
    """Logs endpoint returns 404 for nonexistent task."""
    fake_id = uuid.uuid4()
    resp = await client.get(f"/api/v1/tasks/{fake_id}/logs")
    assert resp.status_code == 404
