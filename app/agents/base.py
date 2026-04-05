"""
BaseAgent — abstract base class for all TaskForge agents.

Each agent:
- Has a name and a system prompt
- Declares which tools it can use
- Runs a function-calling loop: LLM → tool call → result → repeat → final answer
- Logs every step to agent_logs
- Returns a standardised AgentResult
"""

from __future__ import annotations

import logging
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional

from app.config import settings
from app.llm.gemini_client import gemini_client
from app.tools.registry import tool_registry

logger = logging.getLogger(__name__)


@dataclass
class AgentResult:
    """Standardised output from any agent run."""
    agent_name: str
    success: bool
    output: dict[str, Any]
    reasoning: str = ""
    token_usage: int = 0
    iterations: int = 0
    error: Optional[str] = None


class BaseAgent(ABC):
    """
    Abstract base class for all agents.

    Subclasses must define:
    - name: agent identifier
    - system_prompt: the LLM system instruction
    - available_tools: list of tool names from the registry

    Subclasses may override `run` if they need custom orchestration beyond
    the default function-calling loop.
    """

    name: str = "base"
    system_prompt: str = "You are a helpful AI agent."
    available_tools: list[str] = []

    def __init__(self):
        self.max_iterations = settings.max_agent_iterations

    def _build_tool_declarations(self) -> list[dict[str, Any]]:
        """Get Gemini function declarations for this agent's tools."""
        return tool_registry.get_declarations(self.available_tools)

    async def _log_step(
        self,
        task_id: uuid.UUID,
        action: str,
        input_data: Optional[dict] = None,
        output_data: Optional[dict] = None,
        reasoning: Optional[str] = None,
        token_usage: int = 0,
    ) -> None:
        """Persist an agent log entry to the database."""
        try:
            from app.db.database import async_session_factory
            from app.db.repositories import AgentLogRepository

            async with async_session_factory() as session:
                repo = AgentLogRepository(session)
                await repo.create(
                    task_id=task_id,
                    agent_name=self.name,
                    action=action,
                    input_data=input_data,
                    output_data=output_data,
                    reasoning=reasoning,
                    token_usage=token_usage,
                )
        except Exception as e:
            # Non-fatal — logging failure shouldn't crash the agent
            logger.warning(f"[{self.name}] Failed to write agent log: {e}")

    async def run_tool_loop(
        self,
        prompt: str,
        task_id: uuid.UUID,
        extra_context: str = "",
    ) -> AgentResult:
        """
        Execute the function-calling loop:
        1. Send prompt + tools to Gemini
        2. If Gemini calls a tool → execute it → append result → repeat
        3. If Gemini returns text → that is the final answer
        4. Enforce max_iterations guard

        Args:
            prompt: The initial user prompt for this agent
            task_id: Task UUID for logging
            extra_context: Optional additional context to inject into the prompt

        Returns:
            AgentResult
        """
        full_prompt = prompt
        if extra_context:
            full_prompt = f"{extra_context}\n\n{prompt}"

        tool_declarations = self._build_tool_declarations()
        total_tokens = 0
        reasoning_steps: list[str] = []

        await self._log_step(
            task_id=task_id,
            action="start",
            input_data={"prompt_length": len(full_prompt), "tools": self.available_tools},
        )

        # Build conversation history as a simple string for now
        # (stateless; each iteration sends accumulated context)
        conversation = full_prompt

        for iteration in range(self.max_iterations):
            logger.info(f"[{self.name}] iteration {iteration + 1}/{self.max_iterations}")

            try:
                if tool_declarations:
                    response = await gemini_client.generate_with_tools(
                        prompt=conversation,
                        system_instruction=self.system_prompt,
                        tools=tool_declarations,
                    )
                else:
                    response = await gemini_client.generate(
                        prompt=conversation,
                        system_instruction=self.system_prompt,
                    )
                    response["function_calls"] = None
            except Exception as e:
                logger.exception(f"[{self.name}] LLM call failed: {e}")
                return AgentResult(
                    agent_name=self.name,
                    success=False,
                    output={},
                    error=str(e),
                    token_usage=total_tokens,
                    iterations=iteration + 1,
                )

            total_tokens += response.get("token_usage", 0)
            function_calls = response.get("function_calls")

            if not function_calls:
                # Final text answer
                final_text = response.get("text", "") or ""
                reasoning_steps.append(f"[Final] {final_text[:200]}")

                await self._log_step(
                    task_id=task_id,
                    action="complete",
                    output_data={"text_length": len(final_text)},
                    reasoning=final_text[:500],
                    token_usage=total_tokens,
                )

                return AgentResult(
                    agent_name=self.name,
                    success=True,
                    output={"text": final_text},
                    reasoning="\n".join(reasoning_steps),
                    token_usage=total_tokens,
                    iterations=iteration + 1,
                )

            # Execute each tool call
            tool_results_text = []
            for fc in function_calls:
                tool_name = fc["name"]
                tool_args = fc.get("args", {})

                reasoning_steps.append(f"[Tool call] {tool_name}({tool_args})")
                logger.info(f"[{self.name}] calling tool: {tool_name} args={tool_args}")

                # Route tool calls through MCP protocol (falls back to direct registry)
                from app.mcp_client import call_tool_via_mcp
                tool_result = await call_tool_via_mcp(tool_name, tool_args)

                reasoning_steps.append(f"[Tool result] {str(tool_result)[:200]}")

                await self._log_step(
                    task_id=task_id,
                    action=f"tool:{tool_name}",
                    input_data={"tool": tool_name, "args": tool_args},
                    output_data=tool_result,
                    token_usage=0,
                )

                tool_results_text.append(
                    f"Tool '{tool_name}' returned:\n{tool_result}"
                )

            # Append tool results to conversation for next iteration
            conversation = f"{conversation}\n\nTool results:\n" + "\n\n".join(tool_results_text)
            conversation += "\n\nBased on these tool results, continue your analysis."

        # Max iterations reached
        logger.warning(f"[{self.name}] max iterations reached ({self.max_iterations})")
        return AgentResult(
            agent_name=self.name,
            success=False,
            output={},
            error=f"Max iterations ({self.max_iterations}) reached without final answer.",
            reasoning="\n".join(reasoning_steps),
            token_usage=total_tokens,
            iterations=self.max_iterations,
        )

    @abstractmethod
    async def run(self, task_id: uuid.UUID, task_title: str, task_description: str, context: str = "") -> AgentResult:
        """Entry point for agent execution. Subclasses must implement this."""
        ...
