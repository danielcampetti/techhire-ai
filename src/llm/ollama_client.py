"""Async HTTP client for the local Ollama LLM server.

Supports both blocking (full response) and streaming generation modes.
Model is configurable via environment variable OLLAMA_MODEL.
"""
from __future__ import annotations

import json
from typing import AsyncGenerator, Optional

import httpx

from src.config import settings


async def generate(prompt: str, model: Optional[str] = None) -> str:
    """Send a prompt to Ollama and return the complete response text.

    Args:
        prompt: The assembled prompt string.
        model: Optional model override. Defaults to settings.ollama_model.

    Returns:
        The LLM's complete response as a string.

    Raises:
        httpx.HTTPStatusError: If Ollama returns a non-2xx status.
        httpx.ConnectError: If Ollama is not reachable.
    """
    _model = model or settings.ollama_model
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            f"{settings.ollama_url}/api/generate",
            json={"model": _model, "prompt": prompt, "stream": False},
        )
        response.raise_for_status()
        return response.json()["response"]


async def generate_stream(
    prompt: str,
    model: Optional[str] = None,
) -> AsyncGenerator[str, None]:
    """Stream tokens from Ollama as they are generated.

    Args:
        prompt: The assembled prompt string.
        model: Optional model override. Defaults to settings.ollama_model.

    Yields:
        Token strings as they arrive from the LLM.
    """
    _model = model or settings.ollama_model
    async with httpx.AsyncClient(timeout=120.0) as client:
        async with client.stream(
            "POST",
            f"{settings.ollama_url}/api/generate",
            json={"model": _model, "prompt": prompt, "stream": True},
        ) as response:
            async for line in response.aiter_lines():
                if not line:
                    continue
                data = json.loads(line)
                if not data.get("done"):
                    yield data.get("response", "")
