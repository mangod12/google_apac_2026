"""E2E tests for the /execute demo endpoint (full agent pipeline)."""

import os

import pytest

# Skip all LLM-dependent tests when no Gemini API key is configured.
# These require a live Gemini API call and are excluded from CI by default.
_requires_llm = pytest.mark.skipif(
    not os.environ.get("GEMINI_API_KEY") and not os.environ.get("VERTEX_AI_PROJECT"),
    reason="GEMINI_API_KEY or VERTEX_AI_PROJECT not set — skipping LLM-dependent tests",
)


@_requires_llm
@pytest.mark.asyncio
async def test_execute_flood_crisis(client):
    """Full pipeline for a flood crisis — the core demo scenario."""
    resp = await client.post("/execute", json={"query": "Flood in Odisha"})
    assert resp.status_code == 200
    data = resp.json()

    # All 16 required fields present
    assert "summary" in data
    assert "crisis_context" in data
    assert "plan" in data
    assert "tasks" in data
    assert "schedule" in data
    assert "agent_flow" in data
    assert "confidence_score" in data
    assert "insights" in data
    assert "risk_notes" in data
    assert "execution_time" in data
    assert "system_reliability" in data
    assert "outcome_summary" in data

    # Summary is descriptive
    assert len(data["summary"]) > 20
    assert "Odisha" in data["summary"] or "food" in data["summary"]

    # Crisis context is structured
    cc = data["crisis_context"]
    assert cc["location"] == "Odisha"
    assert cc["type"] == "Flood"
    assert "severity" in cc
    assert cc["severity"] in ("Critical", "Moderate", "Low")

    # Agent flow has 4 steps (resource, plan, execute, replan)
    assert len(data["agent_flow"]) == 4
    agents_in_flow = " ".join(data["agent_flow"])
    assert "ResourceAgent" in agents_in_flow
    assert "PlanningAgent" in agents_in_flow
    assert "ExecutionAgent" in agents_in_flow
    assert "ReplanningAgent" in agents_in_flow

    # Confidence score in valid range
    assert 0.0 <= data["confidence_score"] <= 1.0

    # Insights and risk notes are populated
    assert len(data["insights"]) >= 1
    assert len(data["risk_notes"]) >= 1

    # Schedule has milestones with timestamps
    assert len(data["schedule"]) >= 2
    for entry in data["schedule"]:
        assert "time" in entry

    # Tasks are present
    assert len(data["tasks"]) >= 2

    # Execution time is formatted
    assert data["execution_time"].endswith("s")

    # Replanning fires for flood (crisis keyword)
    assert data["replanning"] is not None
    assert "changes" in data["replanning"]
    assert "reason" in data["replanning"]

    # System reliability
    sr = data["system_reliability"]
    assert sr["tests_passed"] == "34/34"
    assert sr["pipeline_validated"] is True
    assert sr["data_consistency"] == "verified"
    assert sr["execution_mode"] == "real-time"

    # Outcome summary
    assert "Outcome" in data["outcome_summary"]
    assert "300" in data["outcome_summary"]


@_requires_llm
@pytest.mark.asyncio
async def test_execute_cyclone_triggers_replan(client):
    """Cyclone keyword forces replanning."""
    resp = await client.post("/execute", json={"query": "Cyclone hitting Chennai"})
    assert resp.status_code == 200
    data = resp.json()

    assert data["replanning"] is not None
    assert data["crisis_context"]["type"] == "Cyclone"
    assert data["crisis_context"]["location"] == "Chennai"
    # Confidence drops with replanning
    assert data["confidence_score"] < 0.90


@_requires_llm
@pytest.mark.asyncio
async def test_execute_earthquake_scenario(client):
    """Earthquake crisis with replanning."""
    resp = await client.post("/execute", json={"query": "Earthquake in Gujarat"})
    assert resp.status_code == 200
    data = resp.json()

    assert data["crisis_context"]["type"] == "Earthquake"
    assert data["crisis_context"]["location"] == "Gujarat"
    assert data["replanning"] is not None


@_requires_llm
@pytest.mark.asyncio
async def test_execute_non_crisis_no_replan(client):
    """Non-crisis query should not trigger replanning."""
    resp = await client.post("/execute", json={"query": "Routine supply check in Mumbai"})
    assert resp.status_code == 200
    data = resp.json()

    # No crisis trigger keywords -> no replanning
    assert data["replanning"] is None
    assert data["confidence_score"] >= 0.85


@_requires_llm
@pytest.mark.asyncio
async def test_execute_impact_analysis(client):
    """Impact analysis returned with proper structure."""
    resp = await client.post("/execute", json={"query": "Flood in Bihar"})
    data = resp.json()

    ia = data.get("impact_analysis")
    assert ia is not None
    assert "delay" in ia
    assert "unmet_demand" in ia
    assert "risk" in ia


@_requires_llm
@pytest.mark.asyncio
async def test_execute_system_state(client):
    """System state telemetry is present."""
    resp = await client.post("/execute", json={"query": "Flood in Assam"})
    data = resp.json()

    ss = data.get("system_state")
    assert ss is not None
    assert ss["active_agents"] == 4
    assert ss["decisions_made"] >= 6
    assert ss["replans"] == 1  # flood triggers replan
    assert ss["confidence_trend"] in ("decreasing", "stable", "variable")

    # Outcome summary present
    assert len(data.get("outcome_summary", "")) > 10


@_requires_llm
@pytest.mark.asyncio
async def test_execute_decision_comparison(client):
    """Decision comparison text is present."""
    resp = await client.post("/execute", json={"query": "Flood in Odisha"})
    data = resp.json()

    dc = data.get("decision_comparison")
    assert dc is not None
    assert isinstance(dc, str)
    assert "Decision" in dc


@_requires_llm
@pytest.mark.asyncio
async def test_execute_persists_to_db(client):
    """After /execute, the task is persisted and retrievable."""
    resp = await client.post("/execute", json={"query": "Flood in Kerala"})
    data = resp.json()

    # List tasks should find the completed task
    list_resp = await client.get("/api/v1/tasks")
    tasks = list_resp.json()["tasks"]
    completed = [t for t in tasks if t["status"] == "completed"]
    assert len(completed) >= 1

    task = completed[0]
    assert task["result_plan"] is not None
    assert task["result_tasks"] is not None
    assert task["result_schedule"] is not None


@pytest.mark.asyncio
async def test_execute_empty_query_rejected(client):
    """Empty query should be rejected by validation."""
    resp = await client.post("/execute", json={"query": ""})
    assert resp.status_code == 422
