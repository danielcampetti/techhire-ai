"""Tests that agents thread the provider parameter to llm_router."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.retrieval.query_engine import RetrievedChunk


@pytest.fixture()
def tmp_db(tmp_path, monkeypatch):
    """Redirect DB to a temp file and create all tables."""
    import src.database.connection as conn_mod
    from src.database.seed import init_db
    monkeypatch.setattr(conn_mod.settings, "db_path", str(tmp_path / "test.db"))
    init_db()
    yield str(tmp_path / "test.db")


def _mock_chunk():
    return RetrievedChunk(
        content="Lucas Mendes — 5 anos de experiência em Python e RAG.",
        score=0.95,
        metadata={"source": "lucas_mendes.pdf", "page": 1},
    )


@pytest.mark.asyncio
async def test_resume_agent_passes_provider_to_router():
    mock_gen = AsyncMock(return_value="resposta")
    with patch("src.agents.resume_agent.retrieve", return_value=[_mock_chunk()]), \
         patch("src.agents.resume_agent.build_prompt", return_value="prompt"), \
         patch("src.agents.resume_agent.llm_router.generate", mock_gen):
        from src.agents.resume_agent import ResumeAgent
        agent = ResumeAgent()
        resp = await agent.answer("Qual a experiência do candidato?", provider="claude")
    mock_gen.assert_awaited_once_with("prompt", provider="claude")
    assert resp.answer == "resposta"


@pytest.mark.asyncio
async def test_resume_agent_default_provider_is_ollama():
    mock_gen = AsyncMock(return_value="resp")
    with patch("src.agents.resume_agent.retrieve", return_value=[_mock_chunk()]), \
         patch("src.agents.resume_agent.build_prompt", return_value="prompt"), \
         patch("src.agents.resume_agent.llm_router.generate", mock_gen):
        from src.agents.resume_agent import ResumeAgent
        agent = ResumeAgent()
        await agent.answer("Qual a experiência do candidato?")
    mock_gen.assert_awaited_once_with("prompt", provider="ollama")


@pytest.mark.asyncio
async def test_match_agent_passes_provider_to_router(tmp_db):
    from src.agents.match_agent import MatchAgent
    with patch("src.agents.match_agent.llm_router.generate", new_callable=AsyncMock, side_effect=["SELECT 1", "interpretação"]) as mock_gen, \
         patch("src.agents.match_agent._execute_sql", return_value=([(1,)], ["count"])):
        agent = MatchAgent()
        resp = await agent.answer("Quantos candidatos?", provider="claude")
    assert mock_gen.await_count == 2
    for call in mock_gen.await_args_list:
        assert call.kwargs.get("provider") == "claude"


@pytest.mark.asyncio
async def test_coordinator_threads_provider_to_resume_agent():
    from src.agents.coordinator import CoordinatorAgent

    mock_r_resp = MagicMock()
    mock_r_resp.answer = "resposta currículos"
    mock_r_resp.sources = []
    mock_r_resp.data = None
    mock_r_resp.actions_taken = []
    mock_r_resp.agent_name = "resume"
    mock_r_resp.chunks_count = 0

    with patch("src.agents.coordinator.init_db"), \
         patch("src.agents.coordinator.CoordinatorAgent._classify", new_callable=AsyncMock, return_value="RESUME"), \
         patch("src.agents.coordinator.audit.log_interaction", new_callable=AsyncMock, return_value=1):
        coordinator = CoordinatorAgent()
        coordinator.resume_agent = MagicMock()
        coordinator.resume_agent.answer = AsyncMock(return_value=mock_r_resp)

        result = await coordinator.process("Qual a experiência do candidato?", provider="claude")

    coordinator.resume_agent.answer.assert_awaited_once_with("Qual a experiência do candidato?", provider="claude", conversation_history=None)
    assert result.provider_utilizado == "claude"
