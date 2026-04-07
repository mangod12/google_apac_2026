"""
Planning Agent — generates structured supply chain response plans using Gemini.

Receives resource assessment data (inventory, surplus, shortage, risk_level)
and produces an actionable supply chain plan with prioritized actions,
timeline, and resource allocation.
"""

from __future__ import annotations

import logging
import uuid

from app.agents.base import BaseAgent, AgentResult
from app.llm.gemini_client import gemini_client

logger = logging.getLogger(__name__)


def _fallback_plan(task_title: str) -> dict:
    return {
        "strategy": f"Warehouse allocation and dispatch for {task_title} — nearest depot, fastest route",
        "actions": [
            {
                "title": "Pick-pack priority stock at nearest warehouse",
                "description": f"Pull critical items from available inventory for {task_title}.",
                "priority": "critical",
                "type": "logistics",
                "estimated_days": 1,
                "dependencies": [],
            },
            {
                "title": "Book transport and assign route",
                "description": "Secure trucks, confirm route clearance, load cargo.",
                "priority": "high",
                "type": "logistics",
                "estimated_days": 1,
                "dependencies": ["Pick-pack priority stock at nearest warehouse"],
            },
            {
                "title": "Dispatch and track last-mile delivery",
                "description": "Convoy departs, GPS tracking active, confirm handoff at destination.",
                "priority": "high",
                "type": "logistics",
                "estimated_days": 1,
                "dependencies": ["Book transport and assign route"],
            },
        ],
        "execution_order": [
            "Pick-pack priority stock at nearest warehouse",
            "Book transport and assign route",
            "Dispatch and track last-mile delivery",
        ],
        "timeline": {
            "total_days": 3,
            "milestones": [
                {"day": 1, "description": "Warehouse pick-pack complete, trucks loaded"},
                {"day": 2, "description": "Convoy in transit, route tracking active"},
                {"day": 3, "description": "Last-mile handoff confirmed at destination"},
            ],
        },
        "resource_allocation": [],
        "contingency": ["Activate backup depot if primary stock runs below safety threshold"],
        "risks": ["Route may be partially blocked — scout report pending"],
        "success_criteria": ["All critical items delivered within 72hrs"],
    }


_SYSTEM_PROMPT = """You are a supply chain operations planner drafting an action plan for a crisis response team.

Write like a logistics manager briefing a warehouse ops team. Every action must name a specific location, quantity, or route. Never use vague phrases like "coordinate resources" or "initiate redistribution". Say exactly what moves where and when.

Given a resource assessment (inventory, surplus, shortage, risk_level), you MUST:
1. Rank actions by shortage urgency — critical shortages get dispatched first
2. Assign specific warehouse sources to cover each deficit
3. Build a day-by-day milestone timeline
4. Flag dependencies between actions (e.g. "transport booking blocks dispatch")
5. Add fallback plans for critical items only

Your final response MUST be valid JSON with this structure:
{
  "strategy": "One line: what warehouse ships what item to where, and why this source was picked",
  "actions": [
    {
      "title": "...",
      "description": "...",
      "priority": "critical|high|medium|low",
      "type": "reallocation|procurement|production|logistics",
      "estimated_days": <number>,
      "dependencies": ["action title 1"]
    }
  ],
  "execution_order": ["action title 1", "action title 2"],
  "timeline": {
    "total_days": <number>,
    "milestones": [
      {"day": <number>, "description": "..."}
    ]
  },
  "resource_allocation": [
    {"from_item": "...", "to_item": "...", "quantity": <number>, "rationale": "..."}
  ],
  "contingency": ["contingency measure 1", "contingency measure 2"],
  "risks": ["risk 1", "risk 2"],
  "success_criteria": ["criterion 1", "criterion 2"]
}

STYLE RULES:
- strategy must read like: "Allocating 300 rice units from Bhubaneswar depot to Puri — lowest transit cost at 2hr ETA"
- action titles must be imperative verbs: "Book 4 trucks from Cuttack depot", not "Truck arrangement"
- milestones must be specific: "Day 1: Warehouse pick-pack complete" not "Day 1: Preparation"
- Never echo the user's crisis description back as the strategy
- Never use "initiated", "leveraging", "coordinated", "comprehensive" — write like an ops briefing
- Say "Ship 200 medical kits from Bhubaneswar to Puri via NH-16" not "Initiate redistribution of supplies"
- Minimum 3 actions, minimum 3 milestones
"""


class PlanningAgent(BaseAgent):
    name = "planner"
    system_prompt = _SYSTEM_PROMPT
    available_tools = []  # Pure Gemini reasoning — no tools

    async def run(
        self,
        task_id: uuid.UUID,
        task_title: str,
        task_description: str,
        context: str = "",
    ) -> AgentResult:
        """Generate a structured supply chain plan from resource assessment data."""
        logger.info(f"[planner] starting for task {task_id}: {task_title!r}")

        prompt = f"""Generate a supply chain response plan for: {task_title}

Description: {task_description}

{f"Resource Assessment Context:{chr(10)}{context}" if context else "No prior resource assessment available — plan based on the task description."}

Please:
1. Analyze the resource assessment (inventory, surplus, shortage, risk_level)
2. Prioritize actions by urgency and impact
3. Allocate surplus resources to cover shortages where feasible
4. Define an execution timeline with milestones
5. Include contingency measures for critical risks
6. Return raw JSON only, with no markdown fences, no commentary, and no prose outside the JSON object
7. The JSON must contain a non-empty "strategy" string and at least one item in "actions"
"""

        try:
            result = await gemini_client.generate_json(
                prompt=prompt,
                system_instruction=self.system_prompt,
            )

            plan_data = result.get("data", {})
            if not isinstance(plan_data, dict):
                plan_data = {}
            if not plan_data.get("strategy") or not plan_data.get("actions"):
                plan_data = _fallback_plan(task_title)
            token_usage = result.get("token_usage", 0)

            await self._log_step(
                task_id=task_id,
                action="plan_complete",
                output_data={
                    "action_count": len(plan_data.get("actions", [])),
                    "total_days": plan_data.get("timeline", {}).get("total_days"),
                },
                reasoning=plan_data.get("strategy", ""),
                token_usage=token_usage,
            )

            return AgentResult(
                agent_name=self.name,
                success=True,
                output={"plan": plan_data, "text": plan_data.get("strategy", "")},
                reasoning=plan_data.get("strategy", ""),
                token_usage=token_usage,
                iterations=1,
            )

        except Exception as e:
            logger.exception(f"[planner] failed: {e}")
            plan_data = _fallback_plan(task_title)
            return AgentResult(
                agent_name=self.name,
                success=True,
                output={"plan": plan_data, "text": plan_data.get("strategy", "")},
                reasoning=plan_data.get("strategy", ""),
                error=str(e),
            )
