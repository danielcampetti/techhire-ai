"""Tests for SSE streaming endpoint and supporting LLM router."""
from __future__ import annotations

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestLlmRouterStream:

    @pytest.mark.asyncio
    async def test_generate_stream_routes_to_ollama(self):
        """generate_stream yields tokens from ollama when provider=ollama."""
        async def fake_stream(prompt):
            for token in ["Hello", " world"]:
                yield token

        with patch("src.llm.ollama_client.generate_stream", new=fake_stream):
            from src.llm import llm_router
            tokens = []
            async for t in llm_router.generate_stream("test prompt", provider="ollama"):
                tokens.append(t)
            assert tokens == ["Hello", " world"]

    @pytest.mark.asyncio
    async def test_generate_stream_routes_to_claude(self):
        """generate_stream yields tokens from claude when provider=claude."""
        async def fake_stream(prompt):
            for token in ["Olá", " mundo"]:
                yield token

        with patch("src.llm.claude_client.generate_stream", new=fake_stream), \
             patch("src.llm.llm_router.settings") as mock_settings:
            mock_settings.anthropic_api_key = "sk-test"
            from src.llm import llm_router
            tokens = []
            async for t in llm_router.generate_stream("test prompt", provider="claude"):
                tokens.append(t)
            assert tokens == ["Olá", " mundo"]
