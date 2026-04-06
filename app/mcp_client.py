"""
MCP Client — connects to the embedded MCP server to call tools via MCP protocol.

Uses SSE transport to connect to the MCP server mounted on the same FastAPI app.
Falls back to direct tool_registry.execute() if MCP connection fails.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


def _get_mcp_sse_url() -> str:
    from app.config import settings
    host = os.getenv("MCP_HOST", "127.0.0.1")
    return f"http://{host}:{settings.port}/mcp/sse"


async def call_tool_via_mcp(name: str, args: dict[str, Any]) -> dict[str, Any]:
    """Call a tool through the MCP protocol (SSE transport).

    Falls back to direct tool_registry.execute() if MCP is unavailable.
    """
    try:
        from mcp.client.sse import sse_client
        from mcp import ClientSession

        async with sse_client(_get_mcp_sse_url(), timeout=10, sse_read_timeout=30) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                result = await session.call_tool(name, args)

                if result.content:
                    text = result.content[0].text
                    try:
                        return json.loads(text)
                    except (json.JSONDecodeError, TypeError):
                        return {"result": text}
                return {"result": "empty"}

    except Exception as e:
        logger.warning(f"[mcp_client] MCP call failed for '{name}', using direct registry: {e}")
        from app.tools.registry import tool_registry
        result = await tool_registry.execute(name, args)
        if isinstance(result, dict):
            result["_mcp_fallback"] = True
            return result
        logger.warning(
            f"[mcp_client] Tool '{name}' returned non-dict fallback type: {type(result).__name__}"
        )
        return {"result": result, "_mcp_fallback": True}
