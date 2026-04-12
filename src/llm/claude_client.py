"""Async client for the Anthropic Claude API.

Same interface as ollama_client.py — drop-in replacement for the LLM
generation layer.  Uses prompt caching on the system prompt to reduce
token costs when the same regulatory context is reused across requests.
"""
from __future__ import annotations

import anthropic
from typing import AsyncGenerator, Optional

from src.config import settings


def _get_client() -> anthropic.AsyncAnthropic:
    api_key = settings.anthropic_api_key
    if not api_key:
        raise ValueError(
            "ANTHROPIC_API_KEY nao configurado. "
            "Defina a variavel de ambiente ou adicione ao arquivo .env."
        )
    return anthropic.AsyncAnthropic(api_key=api_key)


async def generate(prompt: str, model: Optional[str] = None) -> str:
    """Send a prompt to Claude and return the complete response text.

    The system portion of the prompt is sent with cache_control so repeated
    calls with the same regulatory context hit the prompt cache.

    Args:
        prompt: The assembled prompt string (system + context + question).
        model: Optional model override. Defaults to settings.claude_model.

    Returns:
        The LLM's complete response as a string.

    Raises:
        anthropic.APIError: If the Anthropic API returns an error.
        ValueError: If ANTHROPIC_API_KEY is not set.
    """
    _model = model or settings.claude_model
    client = _get_client()

    # Split the prompt into system instructions (before CONTEXTO) and user content.
    # This lets us cache the stable system instructions block separately.
    split_marker = "CONTEXTO REGULATÓRIO:"
    if split_marker in prompt:
        system_part, user_part = prompt.split(split_marker, 1)
        system_content = system_part.strip()
        user_content = f"{split_marker}{user_part}"
    else:
        system_content = ""
        user_content = prompt

    kwargs: dict = {
        "model": _model,
        "max_tokens": 1024,
        "messages": [{"role": "user", "content": user_content}],
    }

    if system_content:
        kwargs["system"] = [
            {
                "type": "text",
                "text": system_content,
                "cache_control": {"type": "ephemeral"},
            }
        ]

    response = await client.messages.create(**kwargs)
    return response.content[0].text


async def generate_json(prompt: str, system_prompt: str = "") -> dict:
    """Send a prompt to Claude and parse the response as JSON.

    Strips markdown code fences (```json ... ```) before parsing.

    Args:
        prompt: Should instruct Claude to respond with JSON only.
        system_prompt: Optional system prompt string (not cached).

    Returns:
        Parsed dict from Claude's JSON response.

    Raises:
        ValueError: If ANTHROPIC_API_KEY is not set or JSON parsing fails.
    """
    import json
    import re as _re

    client = _get_client()

    kwargs: dict = {
        "model": settings.claude_model,
        "max_tokens": 1024,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system_prompt:
        kwargs["system"] = system_prompt

    response = await client.messages.create(**kwargs)
    raw = response.content[0].text.strip()

    # Strip markdown fences
    raw = _re.sub(r"^```(?:json)?\s*", "", raw, flags=_re.IGNORECASE)
    raw = _re.sub(r"\s*```$", "", raw)

    try:
        return json.loads(raw.strip())
    except json.JSONDecodeError as exc:
        match = _re.search(r"\{.*\}", raw, _re.DOTALL)
        if match:
            return json.loads(match.group())
        raise ValueError(f"Falha ao parsear JSON da resposta Claude: {raw[:200]}") from exc


async def generate_stream(
    prompt: str,
    model: Optional[str] = None,
) -> AsyncGenerator[str, None]:
    """Stream tokens from Claude as they are generated.

    Args:
        prompt: The assembled prompt string.
        model: Optional model override. Defaults to settings.claude_model.

    Yields:
        Token strings as they arrive from the API.
    """
    _model = model or settings.claude_model
    client = _get_client()

    split_marker = "CONTEXTO REGULATÓRIO:"
    if split_marker in prompt:
        system_part, user_part = prompt.split(split_marker, 1)
        system_content = system_part.strip()
        user_content = f"{split_marker}{user_part}"
    else:
        system_content = ""
        user_content = prompt

    kwargs: dict = {
        "model": _model,
        "max_tokens": 1024,
        "messages": [{"role": "user", "content": user_content}],
    }

    if system_content:
        kwargs["system"] = [
            {
                "type": "text",
                "text": system_content,
                "cache_control": {"type": "ephemeral"},
            }
        ]

    async with client.messages.stream(**kwargs) as stream:
        async for text in stream.text_stream:
            yield text
