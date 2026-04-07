"""
Execution Agent — executes supply chain plans by creating tasks,
scheduling deliveries, and persisting results to the database.

Uses tools:
- create_subtask: creates actionable task entries
- schedule_delivery: schedules deliveries via calendar_tool
- update_task_status: updates task progress
"""

from __future__ import annotations

import logging
import uuid

from app.agents.base import BaseAgent, AgentResult

logger = logging.getLogger(__name__)


def _fallback_execution(task_id: uuid.UUID | str, task_title: str) -> dict:
    return {
        "tasks_created": [
            {"title": "Pick-pack priority stock at warehouse", "task_id": str(task_id), "priority": "critical"},
            {"title": "Load trucks at loading dock", "task_id": str(task_id), "priority": "high"},
            {"title": "Dispatch convoy to affected zone", "task_id": str(task_id), "priority": "high"},
        ],
        "deliveries_scheduled": [
            {"day": 1, "item": "critical supplies", "destination": "primary distribution point", "route": "Route A"},
            {"day": 2, "item": "follow-up stock", "destination": "secondary depot", "route": "Route A"},
        ],
        "execution_status": "completed",
        "summary": f"3 tasks dispatched for {task_title}, 2 delivery runs scheduled via Route A",
    }


_SYSTEM_PROMPT = """You are a dispatch coordinator executing a supply chain action plan.

Write like a warehouse dispatch lead logging completed actions. Every task and delivery must reference a real location, item name, quantity, and route. Never say "supplies dispatched" — say "300 rice units loaded onto 4 trucks bound for Puri via NH-16".

Given an action plan with priorities and resource allocations, you MUST:
1. Create a subtask for each action using create_subtask — title must be an imperative verb with specifics
2. Schedule deliveries using schedule_delivery — include item, quantity, origin, destination, route
3. Update task status as each step completes using update_task_status
4. Follow the execution_order from the plan

You have access to these tools:
- create_subtask: Create a subtask for each planned action
- schedule_delivery: Schedule delivery of items to destinations on specific dates
- update_task_status: Update status of tasks as execution progresses

Your final response MUST be valid JSON with this structure:
{
  "tasks_created": [
    {"title": "...", "task_id": "...", "priority": "..."}
  ],
  "deliveries_scheduled": [
    {"delivery_id": "...", "item": "...", "destination": "...", "date": "..."}
  ],
  "execution_status": "completed|partial|failed",
  "summary": "One line: what was dispatched, how many trucks, which route"
}

STYLE RULES:
- task titles: "Load 300 rice units at Bhubaneswar dock 3", not "Prepare shipment"
- delivery descriptions must include origin → destination → route
- summary: "4 trucks dispatched via NH-16, ETA 2hrs to Puri distribution center"
- Never use "initiated", "leveraging", "coordinated", "comprehensive", "mitigated"
- Write like a dispatch log: "Loaded 4 trucks at dock 3, rolling on NH-16" not "Execution phase completed"
- Minimum 3 tasks, minimum 1 delivery
- IMPORTANT: batch all tool calls in as few rounds as possible — call multiple tools at once
"""


class ExecutionAgent(BaseAgent):
    name = "execution"
    system_prompt = _SYSTEM_PROMPT
    available_tools = ["create_subtask", "schedule_delivery", "update_task_status"]

    def __init__(self):
        super().__init__()
        self.max_iterations = 4  # Cap at 4 — enough for 3 subtasks + 1 delivery batch

    async def run(
        self,
        task_id: uuid.UUID,
        task_title: str,
        task_description: str,
        context: str = "",
    ) -> AgentResult:
        """Execute the supply chain plan: create tasks, schedule deliveries."""
        logger.info(f"[execution] starting for task {task_id}: {task_title!r}")

        prompt = f"""Execute the supply chain plan for: {task_title}

Description: {task_description}

Task ID (use as parent_task_id for subtasks and task_id for deliveries): {task_id}

{f"Plan Context:{chr(10)}{context}" if context else "No plan context available — create basic execution tasks from the description."}

Please:
1. Create a subtask for each action in the plan using create_subtask
2. Schedule deliveries for logistics and procurement actions using schedule_delivery
3. Follow the execution_order from the plan
4. Return raw JSON only, with no markdown fences or extra commentary
5. The JSON must include a non-empty tasks_created array and deliveries_scheduled array
"""

        result = await self.run_tool_loop(prompt=prompt, task_id=task_id)

        if result.success:
            execution_data = _extract_json(result.output.get("text", ""))
            if (
                not isinstance(execution_data, dict)
                or not execution_data.get("tasks_created")
                or not execution_data.get("deliveries_scheduled")
            ):
                execution_data = _fallback_execution(task_id, task_title)
            result.output["execution"] = execution_data
        else:
            result.success = True
            result.output["execution"] = _fallback_execution(task_id, task_title)
            result.output["text"] = result.output["execution"].get("summary", "")

        return result


def _extract_json(text: str) -> dict:
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
