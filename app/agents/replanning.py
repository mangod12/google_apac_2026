"""
Replanning Agent — triggered when risk_level is "critical".

Adjusts the existing supply chain plan and schedule to mitigate critical risks.
Uses Gemini to reason about plan adjustments without direct tool calls.
"""

from __future__ import annotations

import logging
import uuid

from app.agents.base import BaseAgent, AgentResult

logger = logging.getLogger(__name__)


_SYSTEM_PROMPT = """You are an emergency logistics coordinator adjusting a failed or at-risk delivery plan.

Write like an ops manager filing a plan amendment after a route blockage or supply disruption. Be specific about what changed and why. Never say "adjusted plan for critical risk" — say "Rerouted via NH-59 after NH-16 flooding reported, ETA +3hrs".

You are triggered when risk_level is "critical" BEFORE execution begins. Given the current plan and resource state, you MUST amend the plan so execution uses the corrected version:
1. Use find_alternative_routes to get real driving alternatives between origin and destination — pass blocked roads in avoid_roads
2. Use find_nearest_hubs at the destination to find airports/ports for airlift or sea freight
3. Compare road detour ETA vs. airlift ETA vs. sea option and pick the best combination
4. Reroute, reschedule, or swap warehouse sources with exact alternatives using real distances and ETAs from the tools
5. Add emergency measures (airlift, sea freight) only if road rerouting ETA is too long
6. Update the timeline with new ETAs per milestone based on real route data
7. Define escalation contacts/steps if the adjusted plan also fails

Your final response MUST be valid JSON with this structure:
{
  "adjusted_actions": [
    {
      "original_title": "...",
      "adjusted_title": "...",
      "change_type": "rerouted|rescheduled|source_swapped|cancelled|added",
      "reason": "...",
      "new_priority": "critical|high|medium|low",
      "new_estimated_days": <number>
    }
  ],
  "emergency_measures": [
    {"action": "...", "rationale": "...", "timeline_days": <number>}
  ],
  "resource_reallocation": [
    {"from_item": "...", "to_item": "...", "quantity": <number>, "rationale": "..."}
  ],
  "adjusted_timeline": {
    "total_days": <number>,
    "milestones": [
      {"day": <number>, "description": "..."}
    ]
  },
  "escalation_steps": ["step 1", "step 2"],
  "risk_mitigation_summary": "One line: what broke, what was swapped, new ETA"
}

STYLE RULES:
- change reasons must be specific: "NH-16 bridge submerged, 4hr detour via NH-59" not "route disruption"
- emergency measures: "Airlift 100 medical kits from Kolkata IAF base, 6hr delivery" not "emergency airlift"
- risk_mitigation_summary: "Switched source to Kolkata warehouse, rerouted via NH-59, ETA now 5hrs (+3hrs)" not "Critical risk mitigation applied"
- Never use "initiated", "leveraging", "coordinated approach", "comprehensive", "mitigated"
- Write in plain operational language: "rerouted via X because Y" not "applied mitigation strategy"
- Every action must name a specific road, depot, or airport — no vague references
"""


class ReplanningAgent(BaseAgent):
    name = "replanning"
    system_prompt = _SYSTEM_PROMPT
    available_tools = ["find_alternative_routes", "find_nearest_hubs"]

    async def run(
        self,
        task_id: uuid.UUID,
        task_title: str,
        task_description: str,
        context: str = "",
    ) -> AgentResult:
        """Adjust plan and schedule to mitigate critical risks."""
        logger.info(f"[replanning] starting for task {task_id}: {task_title!r}")

        prompt = f"""CRITICAL RISK detected — amend plan BEFORE execution for: {task_title}

Description: {task_description}

{f"Resource Assessment & Plan:{chr(10)}{context}" if context else "No prior context — propose emergency measures based on the task description."}

Execution has NOT started yet. Your amended plan will be passed directly to the Execution Agent.

Please:
1. Identify which planned actions are blocked or at risk
2. Amend those actions with specific alternatives (reroute, swap source, reschedule)
3. Add emergency measures only if road rerouting is insufficient
4. Update the timeline with amended ETAs per milestone
5. Define escalation steps if the amended plan also fails
6. Return your amended plan as structured JSON
"""

        result = await self.run_tool_loop(prompt=prompt, task_id=task_id)

        if result.success:
            replan_data = _extract_json(result.output.get("text", ""))
            if isinstance(replan_data, dict) and replan_data.get("adjusted_actions"):
                token_usage = result.token_usage
                await self._log_step(
                    task_id=task_id,
                    action="replan_complete",
                    output_data={
                        "adjusted_action_count": len(replan_data.get("adjusted_actions", [])),
                        "emergency_measure_count": len(replan_data.get("emergency_measures", [])),
                    },
                    reasoning=replan_data.get("risk_mitigation_summary", ""),
                    token_usage=token_usage,
                )
                return AgentResult(
                    agent_name=self.name,
                    success=True,
                    output={
                        "replan": replan_data,
                        "text": replan_data.get("risk_mitigation_summary", ""),
                    },
                    reasoning=replan_data.get("risk_mitigation_summary", ""),
                    token_usage=token_usage,
                    iterations=result.iterations,
                )

        # Tool loop failed or returned thin data — let orchestrator inject fallback
        return AgentResult(
            agent_name=self.name,
            success=True,
            output={"replan": {}, "text": ""},
            reasoning="Tool loop returned incomplete replan, orchestrator will apply fallback",
            error=result.error,
        )


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
