"""Unified LLM generation router.

Dispatches generation requests to either Ollama (local, free) or the
Anthropic Claude API based on the ``provider`` argument.  All agents and
API endpoints should call this module instead of calling ollama_client or
claude_client directly.
"""
from __future__ import annotations

from src.config import settings
from src.llm import claude_client, ollama_client


async def generate(prompt: str, provider: str = "ollama") -> str:
    """Route a generation request to the appropriate LLM backend.

    Args:
        prompt: Fully assembled prompt string (includes context + question).
        provider: "ollama" (default, local) or "claude" (Anthropic API).

    Returns:
        The LLM's response as a string.

    Raises:
        ValueError: If provider is "claude" but ANTHROPIC_API_KEY is not set.
        httpx.ConnectError: If provider is "ollama" and Ollama is not reachable.
        anthropic.APIError: If the Claude API returns an error.
    """
    if provider == "claude":
        if not settings.anthropic_api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY não configurado. "
                "Defina a variável de ambiente ou adicione ao .env para usar o Claude."
            )
        return await claude_client.generate(prompt)
    return await ollama_client.generate(prompt)
