"""
MCP Server — exposes all TaskForge tools via the Model Context Protocol.

Mounts on the FastAPI app at /mcp using Streamable HTTP transport.
Tools: create_subtask, update_task_status, estimate_effort,
       knowledge_lookup, schedule_delivery, live_weather, disaster_check
Resources: system://tools, system://health
"""

from __future__ import annotations

import logging
from typing import Optional

from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)

mcp = FastMCP("TaskForge MCP Server")


# ── Task Tools ───────────────────────────────────────────


@mcp.tool()
async def create_subtask(
    parent_task_id: str,
    title: str,
    description: str,
    priority: str = "medium",
) -> dict:
    """Create a subtask under an existing parent task.

    Args:
        parent_task_id: UUID of the parent task
        title: Short title for the subtask
        description: Detailed description of what needs to be done
        priority: Priority level — critical, high, medium, or low
    """
    from app.tools.registry import tool_registry
    result = await tool_registry.execute("create_subtask", {
        "parent_task_id": parent_task_id,
        "title": title,
        "description": description,
        "priority": priority,
    })
    return result


@mcp.tool()
async def update_task_status(task_id: str, status: str) -> dict:
    """Update the status of an existing task.

    Args:
        task_id: UUID of the task to update
        status: New status — pending, resource_assessment, planning, executing, replanning, completed, or failed
    """
    from app.tools.registry import tool_registry
    return await tool_registry.execute("update_task_status", {
        "task_id": task_id,
        "status": status,
    })


@mcp.tool()
async def estimate_effort(
    task_description: str,
    complexity: str = "medium",
) -> dict:
    """Estimate effort required for a task based on its description.

    Args:
        task_description: What the task involves
        complexity: Complexity level — low, medium, or high
    """
    from app.tools.registry import tool_registry
    return await tool_registry.execute("estimate_effort", {
        "task_description": task_description,
        "complexity": complexity,
    })


# ── Knowledge Tool ───────────────────────────────────────


@mcp.tool()
async def knowledge_lookup(
    query: str,
    limit: int = 5,
    task_id: Optional[str] = None,
) -> dict:
    """Search stored knowledge and memory entries for relevant context.

    Args:
        query: Search query string
        limit: Maximum number of results to return
        task_id: Optional task UUID to scope the search
    """
    from app.tools.registry import tool_registry
    args = {"query": query, "limit": limit}
    if task_id:
        args["task_id"] = task_id
    return await tool_registry.execute("knowledge_lookup", args)


# ── Calendar Tool ────────────────────────────────────────


@mcp.tool()
async def schedule_delivery(
    task_id: str,
    item: str,
    quantity: int,
    scheduled_date: str,
    destination: str,
    priority: str = "medium",
    notes: str = "",
) -> dict:
    """Schedule a delivery for logistics coordination.

    Args:
        task_id: UUID of the parent task
        item: What is being delivered (e.g., Emergency Food Packs)
        quantity: Number of units or kg to deliver
        scheduled_date: Target delivery date (YYYY-MM-DD)
        destination: Delivery destination name
        priority: Priority — critical, high, medium, or low
        notes: Additional delivery notes (route info, special instructions)
    """
    from app.tools.registry import tool_registry
    return await tool_registry.execute("schedule_delivery", {
        "task_id": task_id,
        "item": item,
        "quantity": quantity,
        "scheduled_date": scheduled_date,
        "destination": destination,
        "priority": priority,
        "notes": notes,
    })


# ── Weather Tools ────────────────────────────────────────


@mcp.tool()
async def live_weather(
    location_name: Optional[str] = None,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
) -> dict:
    """Fetch real-time weather data from Open-Meteo API for a location.

    Returns temperature, humidity, precipitation, wind speed, and flood risk.
    Supports Indian city names: odisha, chennai, gujarat, rajasthan, kerala,
    bihar, assam, mumbai, uttarakhand (and their major cities).

    Args:
        location_name: Indian city or state name for automatic coordinate lookup
        latitude: Latitude (if not using location_name)
        longitude: Longitude (if not using location_name)
    """
    from app.tools.registry import tool_registry
    args = {}
    if location_name:
        args["location_name"] = location_name
    if latitude is not None:
        args["latitude"] = latitude
    if longitude is not None:
        args["longitude"] = longitude
    return await tool_registry.execute("live_weather", args)


@mcp.tool()
async def disaster_check(
    location_name: Optional[str] = None,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
) -> dict:
    """Check for active flood warnings using Open-Meteo Flood API.

    Returns 7-day river discharge forecast and flood alert level
    (normal, elevated, or critical).

    Args:
        location_name: Indian city or state name for automatic coordinate lookup
        latitude: Latitude (if not using location_name)
        longitude: Longitude (if not using location_name)
    """
    from app.tools.registry import tool_registry
    args = {}
    if location_name:
        args["location_name"] = location_name
    if latitude is not None:
        args["latitude"] = latitude
    if longitude is not None:
        args["longitude"] = longitude
    return await tool_registry.execute("disaster_check", args)


# ── Resources ────────────────────────────────────────────


@mcp.resource("system://tools")
def list_available_tools() -> str:
    """List all available tools in the TaskForge MCP server."""
    return (
        "TaskForge MCP Tools:\n"
        "1. create_subtask — Create a subtask under a parent task\n"
        "2. update_task_status — Update task status (pending → completed)\n"
        "3. estimate_effort — Estimate hours/days for a task\n"
        "4. knowledge_lookup — Search stored knowledge and memory\n"
        "5. schedule_delivery — Schedule logistics deliveries\n"
        "6. live_weather — Real-time weather data (Open-Meteo API)\n"
        "7. disaster_check — Flood warnings and river discharge data\n"
    )


@mcp.resource("system://health")
def system_health() -> str:
    """Get TaskForge system health status."""
    return "TaskForge MCP Server: operational | 7 tools registered | Gemini 2.5 Flash"
