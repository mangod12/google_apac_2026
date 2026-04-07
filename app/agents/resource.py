"""
Resource Agent — fetches inventory data and computes supply chain metrics.

Outputs structured JSON:
- inventory: current stock levels per item
- surplus: items with excess stock
- shortage: items with insufficient stock
- risk_level: overall risk assessment (low, medium, high, critical)
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from app.agents.base import BaseAgent, AgentResult

logger = logging.getLogger(__name__)


_SYSTEM_PROMPT = """You are a logistics operations analyst conducting a warehouse inventory audit.

Write like an operations engineer filing a status report. Use concrete numbers, real location names, and warehouse terminology. Never use filler phrases like "initiated", "leveraging", or "coordinated approach".

When given a crisis scenario, you MUST:
1. Use knowledge_lookup to pull existing inventory and resource data
2. Audit stock levels against demand — flag deficits with exact quantities
3. Classify risk: low, medium, high, or critical based on shortage severity and lead times
4. If roads may be blocked (flood, landslide, cyclone), use find_nearest_hubs to identify airports and ports near the crisis zone for airlift or sea freight alternatives

Your final response MUST be valid JSON with this structure:
{
  "inventory": [
    {"item": "...", "current_stock": <int>, "required_stock": <int>, "unit": "..."}
  ],
  "surplus": [
    {"item": "...", "excess_quantity": <int>, "recommendation": "..."}
  ],
  "shortage": [
    {"item": "...", "deficit_quantity": <int>, "urgency": "high|medium|low"}
  ],
  "risk_level": "low|medium|high|critical",
  "risk_factors": ["factor 1", "factor 2"],
  "summary": "One-line status: what is short, by how much, and where"
}

STYLE RULES:
- summary must read like a warehouse status line, e.g. "Rice stock at 40% capacity, 300-unit deficit across 3 district depots"
- Never repeat the user's query text verbatim in the summary
- Use specific item names (rice, medical kits, tarpaulin) not "supplies"
- Include location names when available (district, city, warehouse ID)
- Never use "initiated", "leveraging", "coordinated", "comprehensive" — write plain warehouse status language
- Say "300 rice units short at Puri depot" not "critical shortage identified in target zone"
"""


class ResourceAgent(BaseAgent):
    name = "resource"
    system_prompt = _SYSTEM_PROMPT
    available_tools = ["knowledge_lookup", "live_weather", "disaster_check", "find_nearest_hubs", "disaster_feed"]

    async def run(
        self,
        task_id: uuid.UUID,
        task_title: str,
        task_description: str,
        context: str = "",
    ) -> AgentResult:
        """Fetch inventory data and compute surplus, shortage, risk_level."""
        logger.info(f"[resource] starting for task {task_id}: {task_title!r}")

        prompt = f"""Assess supply chain resources for: {task_title}

Description: {task_description}

Task ID for memory lookup: {task_id}

Please:
1. Use knowledge_lookup to retrieve any existing inventory or resource data
2. Analyze current stock levels against requirements
3. Identify surplus items (excess stock) and shortage items (deficit)
4. Compute an overall risk_level based on shortages and urgency
5. Return your assessment as structured JSON
"""

        if context:
            prompt = f"Prior context:\n{context}\n\n{prompt}"

        result = await self.run_tool_loop(prompt=prompt, task_id=task_id)

        if result.success:
            resource_data = _extract_json(result.output.get("text", ""))
            result.output["resource_assessment"] = resource_data

        return result


def _extract_json(text: str) -> dict[str, Any]:
    """Extract JSON object from text, handling markdown fences."""
    import json

    if not text:
        return {}
    if "```" in text:
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines)
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        return {"raw": text}
    try:
        return json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return {"raw": text[start:end + 1]}
