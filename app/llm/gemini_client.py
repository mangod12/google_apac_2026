"""
Thin async wrapper around the google-genai SDK.
Supports both Gemini Developer API and Vertex AI auth modes.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from google import genai
from google.genai import types

from app.config import settings

logger = logging.getLogger(__name__)


def _build_client() -> genai.Client:
    """Create a genai Client based on config."""
    if settings.use_vertex_ai:
        return genai.Client(
            vertexai=True,
            project=settings.vertex_ai_project,
            location=settings.vertex_ai_location,
        )
    else:
        return genai.Client(api_key=settings.gemini_api_key)


# Module-level singleton (lazy)
_client: Optional[genai.Client] = None


def get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = _build_client()
    return _client


class GeminiClient:
    """High-level interface for Gemini generation with optional function calling."""

    def __init__(self):
        self.model = settings.gemini_model

    async def generate(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        response_mime_type: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Generate text from Gemini.
        Returns {"text": str, "token_usage": int}
        """
        client = get_client()

        config_kwargs: dict[str, Any] = {}
        if system_instruction:
            config_kwargs["system_instruction"] = system_instruction
        if response_mime_type:
            config_kwargs["response_mime_type"] = response_mime_type

        config = types.GenerateContentConfig(**config_kwargs) if config_kwargs else None

        response = client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=config,
        )

        token_usage = 0
        if response.usage_metadata:
            token_usage = getattr(response.usage_metadata, "total_token_count", 0) or 0

        try:
            text = response.text or ""
        except (ValueError, AttributeError):
            text = ""

        return {
            "text": text,
            "token_usage": token_usage,
        }

    async def generate_json(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Generate and parse JSON output from Gemini.
        Returns {"data": dict|list, "token_usage": int}
        """
        result = await self.generate(
            prompt=prompt,
            system_instruction=system_instruction,
            response_mime_type="application/json",
        )

        text = result["text"].strip()

        # Strip markdown fences if present
        if text.startswith("```"):
            lines = text.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            text = "\n".join(lines)

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            logger.warning("Failed to parse JSON from Gemini response, returning raw text")
            data = {"raw_response": text}

        return {
            "data": data,
            "token_usage": result["token_usage"],
        }

    async def generate_with_tools(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        tools: Optional[list[dict]] = None,
    ) -> dict[str, Any]:
        """
        Generate with function-calling tools.
        Returns {
            "text": str | None,
            "function_calls": [{"name": str, "args": dict}] | None,
            "token_usage": int
        }
        """
        client = get_client()

        config_kwargs: dict[str, Any] = {}
        if system_instruction:
            config_kwargs["system_instruction"] = system_instruction

        # Convert tool dicts to genai Tool objects
        genai_tools = None
        if tools:
            function_declarations = []
            for tool in tools:
                function_declarations.append(
                    types.FunctionDeclaration(
                        name=tool["name"],
                        description=tool.get("description", ""),
                        parameters=tool.get("parameters", None),
                    )
                )
            genai_tools = [types.Tool(function_declarations=function_declarations)]
            config_kwargs["tools"] = genai_tools

        config = types.GenerateContentConfig(**config_kwargs) if config_kwargs else None

        response = client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=config,
        )

        token_usage = 0
        if response.usage_metadata:
            token_usage = getattr(response.usage_metadata, "total_token_count", 0) or 0

        # Check for function calls in response
        function_calls = []
        parts = None
        if response.candidates:
            content = getattr(response.candidates[0], "content", None)
            if content:
                parts = getattr(content, "parts", None)
        if parts:
            for part in parts:
                if part.function_call:
                    function_calls.append({
                        "name": part.function_call.name,
                        "args": dict(part.function_call.args) if part.function_call.args else {},
                    })

        try:
            text = response.text if not function_calls else None
        except (ValueError, AttributeError):
            text = None

        return {
            "text": text,
            "function_calls": function_calls if function_calls else None,
            "token_usage": token_usage,
        }


# Module-level singleton
gemini_client = GeminiClient()
