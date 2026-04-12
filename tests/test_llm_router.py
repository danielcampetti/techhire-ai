"""Tests for the unified LLM router."""
import pytest
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_route_ollama_calls_ollama_client():
    with patch("src.llm.llm_router.ollama_client.generate", new_callable=AsyncMock, return_value="resp") as mock_ollama:
        from src.llm import llm_router
        import importlib; importlib.reload(llm_router)
        result = await llm_router.generate("prompt", provider="ollama")
    mock_ollama.assert_awaited_once_with("prompt")
    assert result == "resp"


@pytest.mark.asyncio
async def test_route_claude_calls_claude_client():
    with patch("src.llm.llm_router.claude_client.generate", new_callable=AsyncMock, return_value="claude resp") as mock_claude, \
         patch("src.llm.llm_router.settings") as mock_settings:
        mock_settings.anthropic_api_key = "sk-test"
        from src.llm import llm_router
        import importlib; importlib.reload(llm_router)
        result = await llm_router.generate("prompt", provider="claude")
    mock_claude.assert_awaited_once_with("prompt")
    assert result == "claude resp"


@pytest.mark.asyncio
async def test_route_claude_without_api_key_raises():
    from src.llm import llm_router
    with patch.object(llm_router, "settings") as mock_settings:
        mock_settings.anthropic_api_key = None
        with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
            await llm_router.generate("prompt", provider="claude")


@pytest.mark.asyncio
async def test_default_provider_is_ollama():
    with patch("src.llm.llm_router.ollama_client.generate", new_callable=AsyncMock, return_value="ok") as mock_ollama:
        from src.llm import llm_router
        import importlib; importlib.reload(llm_router)
        await llm_router.generate("prompt")
    mock_ollama.assert_awaited_once()
